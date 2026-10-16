"""Filtro barato (sin LLM) para no gastar tokens en ofertas obviamente malas."""
from __future__ import annotations

import re
import unicodedata

from .profile import Profile
from .sources import Job


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower())


def _has(haystack: str, needle: str) -> bool:
    return re.search(rf"\b{re.escape(norm(needle))}\b", haystack) is not None


def hard_reject(job: Job, profile: Profile) -> str | None:
    """Motivo de descarte o None si pasa."""
    text = norm(f"{job.title} {job.description}")
    for kw in profile.exclude_keywords:
        if _has(text, kw):
            return f"contiene '{kw}'"
    for db in profile.dealbreakers:
        if _has(text, db):
            return f"dealbreaker '{db}'"
    if profile.locations and not (job.remote and profile.remote_ok):
        loc = norm(f"{job.location} {job.title}")
        if loc.strip() and not any(_has(loc, l) for l in profile.locations):
            return f"ubicación '{job.location}'"
    if profile.min_salary and job.salary_max and job.salary_max < profile.min_salary \
            and (not job.salary_currency or job.salary_currency == profile.salary_currency):
        return f"salario máx {job.salary_max:g} < {profile.min_salary:g}"
    return None


def keyword_score(job: Job, profile: Profile, cv_text: str = "") -> float:
    """0-100. Título objetivo pesa más; luego keywords del perfil y solapamiento con el CV."""
    title = norm(job.title)
    body = norm(job.description)
    score = 0.0
    if any(_has(title, t) for t in profile.target_titles):
        score += 45
    elif any(any(_has(title, w) for w in norm(t).split() if len(w) > 3) for t in profile.target_titles):
        score += 20
    if profile.keywords:
        hits = sum(_has(body, k) or _has(title, k) for k in profile.keywords)
        score += 35 * hits / len(profile.keywords)
    if cv_text:
        cv_words = {w for w in re.findall(r"[a-z][a-z+#.]{2,}", norm(cv_text))}
        job_words = {w for w in re.findall(r"[a-z][a-z+#.]{2,}", body)}
        if job_words:
            score += 20 * min(1.0, len(cv_words & job_words) / max(40, len(job_words) * 0.25))
    return round(min(score, 100.0), 1)


def shortlist(jobs: list[Job], profile: Profile, cv_text: str, limit: int) -> tuple[list[tuple[Job, float]], list[tuple[Job, str]]]:
    kept, rejected = [], []
    for job in jobs:
        reason = hard_reject(job, profile)
        if reason:
            rejected.append((job, reason))
        else:
            kept.append((job, keyword_score(job, profile, cv_text)))
    kept.sort(key=lambda x: x[1], reverse=True)
    return kept[:limit], rejected
