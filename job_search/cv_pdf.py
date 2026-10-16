"""Genera un CV en PDF (A4, una página, fuentes estándar → archivo pequeño) desde un JSON.

    python -m job_search.cv_pdf cv.json salida.pdf [--override oferta.json]

El override reemplaza claves de primer nivel (titulo, perfil, competencias, experiencia...)
para adaptar el CV a una oferta sin tocar el CV base.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BLUE, GREY = HexColor("#2f5496"), HexColor("#9aa9c4")
BASE = ParagraphStyle("b", fontName="Helvetica", fontSize=9.3, leading=12.2)
SMALL = ParagraphStyle("s", parent=BASE, fontSize=8.8, leading=11.6)
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=BLUE)
SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=10.5, leading=14, textColor=BLUE, spaceAfter=6)
PROF = ParagraphStyle("p", parent=BASE, alignment=TA_JUSTIFY, spaceAfter=8)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=BLUE, spaceBefore=8, spaceAfter=3)
H2_FIRST = ParagraphStyle("h2f", parent=H2, spaceBefore=0)
ORG = ParagraphStyle("o", parent=BASE, fontName="Helvetica-Bold", textColor=BLUE, spaceBefore=5)
ROLE = ParagraphStyle("r", parent=BASE, textColor=BLUE)


def _bullets(items, style=BASE):
    return ListFlowable([ListItem(Paragraph(t, style), leftIndent=9, value="•") for t in items],
                        bulletType="bullet", start="•", leftIndent=9, bulletFontSize=7, spaceBefore=1)


def build(cv: dict, out: str | Path) -> None:
    left = [Paragraph("Contacto", H2_FIRST)] + [Paragraph(c, SMALL) for c in cv["contacto"]]
    if cv.get("disponibilidad"):
        left += [Spacer(1, 3), Paragraph(f"<b>Disponibilidad:</b> {cv['disponibilidad']}", SMALL)]
    left.append(Paragraph("Formación", H2))
    for i, f in enumerate(cv["formacion"]):
        if i:
            left.append(Spacer(1, 4))
        left.append(Paragraph(f"<b>{f['titulo']}</b><br/>{f['detalle']}", SMALL))
    left += [Paragraph("Idiomas", H2), _bullets(cv["idiomas"], SMALL),
             Paragraph("Competencias", H2), _bullets(cv["competencias"], SMALL)]

    right = [Paragraph("Experiencia Profesional", H2_FIRST)]
    for i, job in enumerate(cv["experiencia"]):
        right.append(Paragraph(job["org"], ORG if i else ParagraphStyle("o0", parent=ORG, spaceBefore=0)))
        for j, role in enumerate(job["roles"]):
            right.append(Paragraph(role["cargo"], ROLE if not j else ParagraphStyle("r2", parent=ROLE, spaceBefore=3)))
            right.append(_bullets(role["logros"]))
    for sec in cv.get("extra", []):
        right += [Paragraph(sec["titulo"], H2), Paragraph(sec["texto"], BASE)]

    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=12 * mm, title=f"CV {cv['nombre']}", author=cv["nombre"])
    width = A4[0] - 30 * mm - 12  # 12 = padding interno del frame
    table = Table([[left, right]], colWidths=[width * 0.34, width * 0.66])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEAFTER", (0, 0), (0, 0), 0.7, GREY),
                               ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 10),
                               ("LEFTPADDING", (1, 0), (1, 0), 12), ("RIGHTPADDING", (1, 0), (1, 0), 0)]))
    doc.build([Paragraph(cv["nombre"].upper(), H1), Paragraph(cv["titulo"], SUB), Paragraph(cv["perfil"], PROF), table])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cv_json")
    ap.add_argument("out")
    ap.add_argument("--override")
    a = ap.parse_args()
    cv = json.loads(Path(a.cv_json).read_text(encoding="utf-8"))
    if a.override:
        cv |= json.loads(Path(a.override).read_text(encoding="utf-8"))
    build(cv, a.out)


if __name__ == "__main__":
    main()
