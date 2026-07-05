"""Ingesta de transacciones desde emails de notificación bancaria (modelo Kuanto).

Chile no tiene open banking operativo hasta 2026, por lo que la vía gratuita y sin
credenciales es leer los correos de aviso de compra que envían los bancos y
convertirlos en transacciones. Este módulo parsea ese texto de forma robusta.
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from sqlalchemy.orm import Session

from .importers import insert_transaction, parse_amount, parse_date
from .models import Account

# Palabras que indican que el movimiento es un INGRESO (no un gasto).
_INCOME_HINTS = ("abono", "transferencia recibida", "deposito", "devolucion",
                 "reembolso", "te transfirio", "recibiste", "haber")

_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Monto: primero intenta EUR (con símbolo), luego CLP ($ o texto).
_RE_EUR = re.compile(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d+,\d{2})\s*(?:€|eur)", re.I)
_RE_EUR2 = re.compile(r"(?:€|eur)\s*(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d+,\d{2})", re.I)
_RE_CLP = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)")

# Comercio: "en COMERCIO" hasta un delimitador natural.
_RE_MERCHANT = re.compile(
    r"\ben\s+([^\n.,;]+?)(?=\s+(?:el|con|por|a las|el dia|tarjeta|\d{1,2}[/-])|[.,;\n]|$)",
    re.I,
)
_RE_DATE_NUM = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})")
_RE_DATE_ES = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+de\s+(\d{4}))?", re.I)


def _parse_date_es(text: str, fallback: dt.date) -> dt.date:
    m = _RE_DATE_NUM.search(text)
    if m:
        d = parse_date(m.group(1))
        if d:
            return d
    m = _RE_DATE_ES.search(text)
    if m:
        mon = _MONTHS_ES.get(m.group(2).lower())
        if mon:
            year = int(m.group(3)) if m.group(3) else fallback.year
            try:
                return dt.date(year, mon, int(m.group(1)))
            except ValueError:
                pass
    return fallback


def parse_email(
    subject: str,
    body: str,
    sender: str = "",
    received_date: dt.date | None = None,
) -> dict | None:
    """Extrae una transacción desde un email de aviso bancario.

    Devuelve ``{date, description, amount, currency}`` o ``None`` si no logra
    identificar un monto (probablemente no es una notificación de movimiento).
    """
    text = f"{subject}\n{body}".strip()
    low = text.lower()
    fallback = received_date or dt.date.today()

    currency = "CLP"
    amount_str: str | None = None
    for rx in (_RE_EUR, _RE_EUR2):
        m = rx.search(text)
        if m:
            currency, amount_str = "EUR", m.group(1)
            break
    if amount_str is None:
        m = _RE_CLP.search(text)
        if m:
            currency, amount_str = "CLP", m.group(1)
    if amount_str is None:
        return None

    amount = parse_amount(amount_str)
    if amount == 0:
        return None
    # Los avisos de compra son gastos salvo que el texto indique ingreso.
    is_income = any(h in low for h in _INCOME_HINTS)
    amount = abs(amount) if is_income else -abs(amount)

    m = _RE_MERCHANT.search(text)
    merchant = m.group(1).strip() if m else ""
    if not merchant:
        # Fallback: usa el remitente/banco como glosa mínima.
        merchant = (sender.split("@")[-1].split(".")[0] or "Movimiento").upper()
    description = re.sub(r"\s+", " ", merchant)[:120]

    return {
        "date": _parse_date_es(text, fallback),
        "description": description,
        "amount": amount,
        "currency": currency,
    }


def ingest_parsed(
    db: Session, account: Account, parsed: list[dict], source: str = "email"
) -> dict:
    """Inserta transacciones ya parseadas; aplica categorización y dedup."""
    imported = skipped = 0
    for p in parsed:
        tx = insert_transaction(
            db, account, p["date"], p["description"],
            Decimal(str(p["amount"])), source=source, currency=p.get("currency"),
        )
        if tx is None:
            skipped += 1
        else:
            imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped, "total": imported + skipped}
