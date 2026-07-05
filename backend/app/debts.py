"""Importador del informe de deudas CMF / Boletín de Informaciones Comerciales.

Formato oficial (CSV) que puedes descargar desde tu banco o la CMF con tu RUT.
Cada fila es una operación de crédito vigente (consumo, tarjeta, línea, etc.).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
from decimal import Decimal

from sqlalchemy.orm import Session

from .categorize import normalize
from .importers import _decode, _detect_delimiter, parse_amount, parse_date
from .models import Debt

# Mapeo de campos → posibles cabeceras (normalizadas, sin acentos).
_FIELDS = {
    "institution": ["institucion financiera"],
    "credit_type": ["tipo de credito"],
    "code": ["codigo de la operacion"],
    "granted": ["fecha de otorgamiento"],
    "monthly": ["carga financiera"],
    "due": ["fecha vencimiento final pactada en la operacion", "fecha vencimiento"],
    "original": ["monto original de las operacion", "monto original"],
    "current": ["monto actual de la operacion", "monto actual"],
    "at_day": ["monto al dia"],
    "arrears": ["mora actual"],
    "report_date": ["fecha"],
}


def _find(headers: list[str], keys: list[str]) -> str | None:
    norm = [(normalize(h), h) for h in headers]
    for key in keys:  # coincidencia exacta primero
        nk = normalize(key)
        for nh, original in norm:
            if nh == nk:
                return original
    for key in keys:  # luego por contención
        nk = normalize(key)
        for nh, original in norm:
            if nk and nk in nh:
                return original
    return None


def _clean_date(d: dt.date | None) -> dt.date | None:
    # Las tarjetas/líneas traen 01/01/1900 como "sin vencimiento".
    return d if (d and d.year >= 2000) else None


def import_debts_csv(db: Session, data: bytes, filename: str = "") -> dict:
    """Importa (o actualiza) las deudas desde el CSV del informe CMF."""
    text = _decode(data)
    delimiter = _detect_delimiter(text[:4096])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = [h for h in (reader.fieldnames or []) if h]
    if not headers:
        return {"error": "No se detectaron columnas.", "imported": 0}

    cols = {field: _find(headers, keys) for field, keys in _FIELDS.items()}
    if not cols["institution"] or not cols["current"]:
        return {"error": "No parece un informe de deudas (faltan columnas clave).",
                "headers": headers, "imported": 0}

    imported = updated = 0
    for row in reader:
        institution = (row.get(cols["institution"]) or "").strip()
        if not institution:
            continue
        code = (row.get(cols["code"]) or "").strip() if cols["code"] else ""
        current = parse_amount(row.get(cols["current"]))

        payload = dict(
            institution=institution,
            credit_type=(row.get(cols["credit_type"]) or "").strip() if cols["credit_type"] else "",
            code=code,
            original_amount=parse_amount(row.get(cols["original"])) if cols["original"] else Decimal(0),
            current_amount=current,
            at_day_amount=parse_amount(row.get(cols["at_day"])) if cols["at_day"] else current,
            monthly_payment=parse_amount(row.get(cols["monthly"])) if cols["monthly"] else Decimal(0),
            arrears=parse_amount(row.get(cols["arrears"])) if cols["arrears"] else Decimal(0),
            granted_date=parse_date(row.get(cols["granted"])) if cols["granted"] else None,
            due_date=_clean_date(parse_date(row.get(cols["due"]))) if cols["due"] else None,
            report_date=parse_date(row.get(cols["report_date"])) if cols["report_date"] else None,
            currency="CLP",
            source="cmf",
        )

        existing = db.query(Debt).filter(Debt.code == code).first() if code else None
        if existing:
            for key, value in payload.items():
                # No pisar una cuota conocida (editada por el usuario) con un 0 del informe.
                if key == "monthly_payment" and value == 0 and existing.monthly_payment:
                    continue
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(Debt(**payload))
            imported += 1

    db.commit()
    return {"imported": imported, "updated": updated, "total": imported + updated}
