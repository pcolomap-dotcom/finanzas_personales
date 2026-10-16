"""Fuentes de ofertas gratuitas y normalización a un modelo común.

- Get on Board (Chile/LatAm, API pública)
- Remotive (remoto global, API pública)
- Arbeitnow (Europa, API pública)
- Archivos JSON/CSV manuales (pega aquí ofertas de LinkedIn, InfoJobs, Indeed...)
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

USER_AGENT = "finanzas-personales-job-search/0.1"
TIMEOUT = 20


@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    description: str
    location: str = ""
    remote: bool = False
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    published_at: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        key = self.url or f"{self.company}|{self.title}"
        return hashlib.sha1(key.strip().lower().encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self) | {"uid": self.uid}


def strip_html(text: str) -> str:
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------- parsers (puros, testeables) ---------------------------
def parse_getonbrd(payload: dict) -> list[Job]:
    jobs = []
    for item in payload.get("data", []):
        a = item.get("attributes", {})
        company = (((a.get("company") or {}).get("data") or {}).get("attributes") or {}).get("name", "")
        countries = a.get("countries") or []
        desc = " ".join(strip_html(a.get(k) or "") for k in ("description", "functions", "desirable", "benefits"))
        jobs.append(Job(
            source="getonbrd",
            title=a.get("title", ""),
            company=company,
            url=(item.get("links") or {}).get("public_url", ""),
            description=desc.strip(),
            location=", ".join(countries) if isinstance(countries, list) else str(countries),
            remote=bool(a.get("remote")) or a.get("remote_modality") in ("fully_remote", "remote_local"),
            salary_min=a.get("min_salary"),
            salary_max=a.get("max_salary"),
            salary_currency="USD" if a.get("min_salary") else "",
            published_at=str(a.get("published_at") or ""),
        ))
    return jobs


def parse_remotive(payload: dict) -> list[Job]:
    return [Job(
        source="remotive",
        title=j.get("title", ""),
        company=j.get("company_name", ""),
        url=j.get("url", ""),
        description=strip_html(j.get("description", "")),
        location=j.get("candidate_required_location", ""),
        remote=True,
        published_at=j.get("publication_date", ""),
        tags=list(j.get("tags") or []),
    ) for j in payload.get("jobs", [])]


def parse_arbeitnow(payload: dict) -> list[Job]:
    return [Job(
        source="arbeitnow",
        title=j.get("title", ""),
        company=j.get("company_name", ""),
        url=j.get("url", ""),
        description=strip_html(j.get("description", "")),
        location=j.get("location", ""),
        remote=bool(j.get("remote")),
        published_at=str(j.get("created_at", "")),
        tags=list(j.get("tags") or []),
    ) for j in payload.get("data", [])]


def load_file(path: Path) -> list[Job]:
    """JSON (lista de objetos) o CSV con columnas title, company, url, description, location..."""
    if not path.exists():
        return []
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
    jobs = []
    for r in rows:
        jobs.append(Job(
            source=r.get("source") or f"file:{path.name}",
            title=r.get("title", ""),
            company=r.get("company", ""),
            url=r.get("url", ""),
            description=strip_html(r.get("description", "")),
            location=r.get("location", ""),
            remote=str(r.get("remote", "")).lower() in ("1", "true", "yes", "sí", "si"),
            salary_min=float(r["salary_min"]) if r.get("salary_min") else None,
            salary_max=float(r["salary_max"]) if r.get("salary_max") else None,
            salary_currency=r.get("salary_currency", ""),
        ))
    return jobs


# --------------------------- fetchers (red) ---------------------------
def fetch_getonbrd(query: str, per_page: int = 30) -> list[Job]:
    qs = urllib.parse.urlencode({"query": query, "per_page": per_page, "expand": '["company"]'})
    return parse_getonbrd(_get_json(f"https://www.getonbrd.com/api/v0/search/jobs?{qs}"))


def fetch_remotive(query: str, limit: int = 30) -> list[Job]:
    qs = urllib.parse.urlencode({"search": query, "limit": limit})
    return parse_remotive(_get_json(f"https://remotive.com/api/remote-jobs?{qs}"))


def fetch_arbeitnow(_query: str = "", pages: int = 2) -> list[Job]:
    jobs: list[Job] = []
    for page in range(1, pages + 1):
        jobs += parse_arbeitnow(_get_json(f"https://www.arbeitnow.com/api/job-board-api?page={page}"))
    return jobs


def collect(profile, log=print) -> list[Job]:
    """Recorre todas las fuentes activas; una fuente caída no tumba la búsqueda."""
    from .profile import resolve

    jobs: list[Job] = []
    src = profile.sources
    fetchers = []
    for title in profile.target_titles:
        if src.getonbrd:
            fetchers.append(("getonbrd", lambda t=title: fetch_getonbrd(t)))
        if src.remotive:
            fetchers.append(("remotive", lambda t=title: fetch_remotive(t)))
    if src.arbeitnow:
        fetchers.append(("arbeitnow", fetch_arbeitnow))
    for name, fn in fetchers:
        try:
            got = fn()
            log(f"  {name}: {len(got)} ofertas")
            jobs += got
        except Exception as exc:  # red, cambios de API, rate limit...
            log(f"  {name}: error ({exc.__class__.__name__}: {exc})")
    for f in src.files:
        got = load_file(resolve(f))
        log(f"  archivo {f}: {len(got)} ofertas")
        jobs += got
    # dedup por uid
    unique = {j.uid: j for j in jobs if j.title}
    return list(unique.values())
