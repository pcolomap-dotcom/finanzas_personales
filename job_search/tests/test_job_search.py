"""Tests sin red ni API: python job_search/tests/test_job_search.py"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from job_search.__main__ import run_search  # noqa: E402
from job_search.matcher import MatchResult, combined_score, should_apply  # noqa: E402
from job_search.prefilter import hard_reject, keyword_score  # noqa: E402
from job_search.profile import Profile  # noqa: E402
from job_search.sources import Job, parse_arbeitnow, parse_getonbrd, parse_remotive, strip_html  # noqa: E402
from job_search.store import Store  # noqa: E402

PROFILE = Profile(
    cv_path="cv.txt",
    target_titles=["Data Analyst", "Analista de Datos"],
    keywords=["python", "sql", "power bi"],
    exclude_keywords=["prácticas"],
    locations=["Chile", "Madrid"],
    min_salary=30000,
    dealbreakers=["100% comisión"],
)
CV = "Analista de datos con 4 años de experiencia en Python, SQL, Power BI y Excel en banca."


def job(**kw):
    base = dict(source="t", title="Data Analyst", company="Acme", url="https://x/1",
                description="Buscamos Python y SQL", location="Madrid")
    return Job(**(base | kw))


def test_strip_html():
    assert strip_html("<p>Hola&nbsp;<b>mundo</b></p><ul><li>SQL</li></ul>") == "Hola mundo\nSQL"


def test_parsers():
    g = parse_getonbrd({"data": [{"id": "1", "attributes": {
        "title": "Analista de Datos", "description": "<p>SQL</p>", "remote": True, "countries": ["Chile"],
        "min_salary": 1500, "max_salary": 2000,
        "company": {"data": {"attributes": {"name": "Fintual"}}}}, "links": {"public_url": "https://g/1"}}]})
    assert g[0].company == "Fintual" and g[0].remote and g[0].url == "https://g/1" and g[0].location == "Chile"
    r = parse_remotive({"jobs": [{"title": "Data Analyst", "company_name": "R", "url": "https://r/1",
                                  "description": "<b>x</b>", "candidate_required_location": "Worldwide"}]})
    assert r[0].remote and r[0].description == "x"
    a = parse_arbeitnow({"data": [{"title": "BI", "company_name": "A", "url": "https://a/1",
                                   "description": "", "remote": False, "location": "Berlin"}]})
    assert a[0].location == "Berlin"


def test_hard_reject():
    assert hard_reject(job(), PROFILE) is None
    assert "prácticas" in hard_reject(job(title="Prácticas Data Analyst"), PROFILE)
    assert "dealbreaker" in hard_reject(job(description="Sueldo 100% comision"), PROFILE)
    assert "ubicación" in hard_reject(job(location="Berlin"), PROFILE)
    assert hard_reject(job(location="Berlin", remote=True), PROFILE) is None
    assert "salario" in hard_reject(job(salary_max=20000), PROFILE)


def test_keyword_score_ranks_relevant_higher():
    good = keyword_score(job(description="Python, SQL y Power BI en banca"), PROFILE, CV)
    bad = keyword_score(job(title="Chef", description="Cocina mediterránea"), PROFILE, CV)
    assert good > 60 > bad


def _match(c, e, verdict="apply", missing=()):
    return MatchResult(candidate_fit=c, employer_fit=e, must_haves_met=[], must_haves_missing=list(missing),
                       nice_to_haves_met=[], red_flags=[], summary="", verdict=verdict)


def test_two_sided_decision():
    assert should_apply(_match(90, 85), PROFILE)
    assert not should_apply(_match(95, 40), PROFILE)          # me gusta, pero no cumplo
    assert not should_apply(_match(40, 95), PROFILE)          # cumplo, pero no me interesa
    assert not should_apply(_match(90, 85, missing=["a", "b"]), PROFILE)
    assert combined_score(_match(100, 25)) == 50.0


class FakeClient:
    """Imita client.beta.messages.create devolviendo un MatchResult fijo."""
    def __init__(self, result):
        self.calls = 0
        payload = json.dumps(result.model_dump())
        def create(**kwargs):
            self.calls += 1
            assert kwargs["system"][1]["cache_control"] == {"type": "ephemeral"}
            assert "Data Analyst" in kwargs["messages"][0]["content"]
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=payload)])
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))


def test_pipeline_end_to_end_and_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "jobs.db")
        jobs = [job(), job(url="https://x/2", location="Berlin")]
        client = FakeClient(_match(88, 80))
        counts = run_search(PROFILE, CV, store, use_llm=True, rescore=False, jobs=jobs,
                            client=client, log=lambda *_: None)
        assert counts["recommended"] == 1 and client.calls == 1
        assert store.get(jobs[1].uid)["status"] == "filtered"
        # segunda ejecución: nada nuevo → sin llamadas extra al LLM
        run_search(PROFILE, CV, store, use_llm=True, rescore=False, jobs=jobs, client=client, log=lambda *_: None)
        assert client.calls == 1
        assert store.set_status(jobs[0].uid[:8], "applied")
        assert store.get(jobs[0].uid)["status"] == "applied"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
