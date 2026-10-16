"""Informe Markdown de resultados."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .store import DATA_DIR

LABELS = {"recommended": "✅ Postular", "maybe": "🤔 Revisar", "skipped": "⛔ Descartadas por IA"}


def write_report(rows: list[dict], path: Path | None = None) -> Path:
    path = path or DATA_DIR / "report.md"
    lines = [f"# Ofertas evaluadas — {dt.date.today().isoformat()}", ""]
    for status, label in LABELS.items():
        group = [r for r in rows if r["status"] == status]
        if not group:
            continue
        lines += [f"## {label} ({len(group)})", ""]
        for r in group:
            j, m = r["job"], r["match"] or {}
            lines.append(f"### [{j['title']} — {j['company']}]({j['url']})")
            lines.append(
                f"`{r['uid']}` · {j['source']} · {j['location'] or 's/ubicación'}"
                f"{' · remoto' if j['remote'] else ''} · **score {r['score']}** "
                f"(tú {m.get('candidate_fit', '?')} / empleador {m.get('employer_fit', '?')})"
            )
            lines.append("")
            if m.get("summary"):
                lines.append(m["summary"])
            if m.get("must_haves_missing"):
                lines.append(f"- ❌ Te falta: {', '.join(m['must_haves_missing'])}")
            if m.get("must_haves_met"):
                lines.append(f"- ✔️ Cumples: {', '.join(m['must_haves_met'])}")
            if m.get("red_flags"):
                lines.append(f"- 🚩 {', '.join(m['red_flags'])}")
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
