"""CLI del buscador.

    python -m job_search search  [--profile job_search/profile.json] [--no-llm] [--rescore]
    python -m job_search list    [--status recommended maybe]
    python -m job_search pack    <uid>          # carta + respuestas para postular
    python -m job_search mark    <uid> applied|discarded|...
"""
from __future__ import annotations

import argparse
import os
import sys

from .matcher import combined_score, evaluate, heuristic, should_apply
from .prefilter import shortlist
from .profile import load_cv_text, load_profile
from .report import write_report
from .sources import Job, collect
from .store import STATUSES, Store

DEFAULT_PROFILE = "job_search/profile.json"


def _has_credentials() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.environ.get("ANTHROPIC_PROFILE"))


def run_search(profile, cv_text: str, store: Store, *, use_llm: bool, rescore: bool,
               jobs: list[Job] | None = None, client=None, log=print) -> dict:
    log("Buscando ofertas...")
    jobs = jobs if jobs is not None else collect(profile, log=log)
    fresh = [j for j in jobs if rescore or not store.seen(j.uid)]
    log(f"{len(jobs)} ofertas únicas, {len(fresh)} nuevas")

    kept, rejected = shortlist(fresh, profile, cv_text, limit=profile.llm.max_jobs_to_score)
    for job, reason in rejected:
        store.upsert(job.to_dict(), status="filtered", note=reason)
    log(f"Prefiltro: {len(rejected)} descartadas, {len(kept)} pasan a evaluación")

    counts = {"recommended": 0, "maybe": 0, "skipped": 0, "error": 0}
    for i, (job, kw) in enumerate(kept, 1):
        try:
            result = evaluate(job, profile, cv_text, client=client) if use_llm else heuristic(job, profile, kw)
        except Exception as exc:
            log(f"  [{i}/{len(kept)}] error evaluando '{job.title}': {exc}")
            store.upsert(job.to_dict(), status="error", kw_score=kw, note=str(exc))
            counts["error"] += 1
            continue
        if should_apply(result, profile):
            status = "recommended"
        else:
            status = "maybe" if result.verdict != "skip" else "skipped"
        score = combined_score(result)
        store.upsert(job.to_dict(), status=status, kw_score=kw, match=result.model_dump(), score=score)
        counts[status] += 1
        log(f"  [{i}/{len(kept)}] {status:<11} {score:>5}  {job.title} — {job.company}")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="job_search", description="Buscador IA de empleo según tu CV")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="busca y evalúa ofertas nuevas")
    s.add_argument("--no-llm", action="store_true", help="solo heurística (gratis, sin API)")
    s.add_argument("--rescore", action="store_true", help="re-evalúa ofertas ya vistas")
    ls = sub.add_parser("list", help="lista ofertas guardadas")
    ls.add_argument("--status", nargs="*", default=["recommended", "maybe"])
    pk = sub.add_parser("pack", help="genera carta y respuestas para una oferta")
    pk.add_argument("uid")
    mk = sub.add_parser("mark", help="cambia el estado de una oferta")
    mk.add_argument("uid")
    mk.add_argument("status", choices=STATUSES)
    args = ap.parse_args(argv)

    store = Store()
    if args.cmd == "mark":
        ok = store.set_status(args.uid, args.status)
        print("OK" if ok else "No encontrada")
        return 0 if ok else 1
    if args.cmd == "list":
        for r in store.list(tuple(args.status)):
            j = r["job"]
            print(f"{r['uid']}  {r['status']:<11} {r['score'] or '-':>5}  {j['title']} — {j['company']}  {j['url']}")
        return 0

    profile = load_profile(args.profile)
    cv_text = load_cv_text(profile.cv_path)

    if args.cmd == "search":
        use_llm = not args.no_llm
        if use_llm and not _has_credentials():
            print("Aviso: sin ANTHROPIC_API_KEY; se usa modo heurístico (--no-llm).", file=sys.stderr)
            use_llm = False
        counts = run_search(profile, cv_text, store, use_llm=use_llm, rescore=args.rescore)
        path = write_report(store.list(("recommended", "maybe", "skipped")))
        print(f"\nResultado: {counts}\nInforme: {path}")
        return 0

    if args.cmd == "pack":
        from .apply_pack import build_pack

        row = store.get(args.uid)
        if not row:
            print("No encontrada")
            return 1
        data = {k: v for k, v in row["job"].items() if k != "uid"}
        path = build_pack(Job(**data), row["match"], profile, cv_text)
        print(f"Paquete de postulación: {path}\nCuando postules: python -m job_search mark {row['uid']} applied")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
