"""Ingesta de transacciones desde emails de aviso/comprobante bancario (modelo Kuanto).

Los bancos chilenos envían comprobantes HTML con campos etiquetados
("Monto transferido $459", "Recibiste 300000 CLP", "Monto pagado USD$61,11 …
Monto $55.199"). Este módulo extrae de ahí la transacción de forma robusta:
- monto por etiqueta, prefiriendo el importe en CLP (impacto real en la cuenta),
- signo (ingreso/gasto) según el tipo de comprobante,
- fecha numérica o en texto ("27 de abril de 2026"),
- glosa a partir del asunto (limpio y descriptivo),
- descarta cartolas, estados de cuenta, claves y avisos que no son movimientos.
"""
from __future__ import annotations

import datetime as dt
import html
import re
from decimal import Decimal

from sqlalchemy.orm import Session

from .importers import insert_transaction, parse_amount, parse_date
from .models import Account

_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Asuntos que NO son movimientos (resúmenes, seguridad, avisos).
_SKIP = (
    "cartola", "estado de cuenta", "codigo", "clave", "renovacion de deposito",
    "liquidacion de deposito", "bloqueo", "cancelad", "rechazad", "cierre de producto",
    "envio de estado", "puedes ignorar", "solo estamos probando", "notificacion de cambio",
    "aviso de renovacion", "cambio de clave", "recupere su clave", "solicitud de cierre",
)

# El asunto indica un INGRESO (si no, se asume gasto/salida).
_INCOME_SUBJECT = (
    "recibiste", "te ha enviado", "transferencias de fondos de", "transferencia recibida",
    "recibiste una transferencia", "recibiste dinero", "abono de", "deposito de",
)

# Montos por etiqueta (se busca en texto en minúsculas, conservando $ . ,).
_AMOUNT_PATTERNS = (
    r"monto\s+transferido[:\s]*\$?\s*([\d][\d.,]*)",
    r"monto\s+del\s+pago[:\s]*\$?\s*([\d][\d.,]*)",
    r"monto\s+pagado[:\s]*(?:usd\$?|us\$|\$|eur|€)?\s*([\d][\d.,]*)",
    r"monto\s+girado[:\s]*\$?\s*([\d][\d.,]*)",
    r"monto\s+de\s+la\s+transferencia[:\s]*\$?\s*([\d][\d.,]*)",
    r"recibiste\s*(?:un\s+abono\s+de\s*)?\$?\s*([\d][\d.,]*)\s*(clp|usd|eur)?",
    r"enviaste\s*\$?\s*([\d][\d.,]*)",
    r"\bmonto\b[:\s]*\$?\s*([\d][\d.,]*)",
    r"([\d][\d.,]*)\s*(?:€|\beur\b)",   # importes en euros
    r"(?:€|\beur\b)\s*([\d][\d.,]*)",
    r"\$\s*([\d][\d.,]{2,})",  # último recurso (CLP con $)
)

# Comercio en avisos de compra: "compra ... $X en COMERCIO el/con ..."
_RE_MERCHANT = re.compile(
    r"(?:compra\w*|pagaste|pago|giro)\b[^$\n]{0,25}\$?\s*[\d][\d.,]*"
    r"\s+(?:(?:€|eur|clp|usd)\s+)?en\s+"
    r"([a-z0-9][\w .*&'\-]{2,40}?)(?=\s+(?:el|con|por|tarjeta|de\s|\d{1,2}[/-])|[.,;\n]|$)",
    re.I,
)
_MERCHANT_STOP = (
    "linea", "forma", "navegador", "www", "internet", "tu banco", "tu cuenta",
    "el pais", "papel", "detalle", "el sitio", "efectivo", "cuenta global",
)

_RE_DATE_NUM = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")
_RE_DATE_ES = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.I)
_RE_CLEAN_SUBJECT = re.compile(
    r"^(comprobante( de| pago| solicitud)?|aviso( de)?|notificaci[oó]n(\s*-)?|"
    r"tu|hemos realizado)\s+", re.I,
)


def _norm(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def _find_amount(low: str) -> tuple[str, Decimal] | None:
    """Devuelve (moneda, monto). Reúne los montos etiquetados en orden de
    prioridad y prefiere el importe en CLP (impacto real en la cuenta; p. ej. en
    un pago de tarjeta en USD toma el "Monto $55.199" y no el "USD$61,11")."""
    found: list[tuple[str, Decimal]] = []
    for pat in _AMOUNT_PATTERNS:
        for m in re.finditer(pat, low):
            window = low[max(0, m.start() - 5): m.end() + 5]
            if "usd" in window or "us$" in window:
                cur = "USD"
            elif "eur" in window or "€" in window:
                cur = "EUR"
            else:
                cur = "CLP"
            val = parse_amount(m.group(1))
            if val > 0:
                found.append((cur, val))
    if not found:
        return None
    for cur, val in found:  # preferir CLP
        if cur == "CLP":
            return cur, val
    return found[0]


def _find_date(low: str, fallback: dt.date) -> dt.date:
    m = _RE_DATE_NUM.search(low)
    if m:
        d = parse_date(m.group(1))
        if d and d.year >= 2015:  # descarta fechas espurias de footers/números
            return d
    m = _RE_DATE_ES.search(low)
    if m:
        mon = _MONTHS_ES.get(m.group(2).lower())
        if mon:
            try:
                return dt.date(int(m.group(3)), mon, int(m.group(1)))
            except ValueError:
                pass
    return fallback


def _extract_merchant(low: str) -> str | None:
    """Extrae el comercio de un aviso de compra; None si no es una compra clara."""
    m = _RE_MERCHANT.search(low)
    if not m:
        return None
    cand = re.sub(r"\s+", " ", m.group(1)).strip(" .")
    if len(cand) < 3 or any(stop in cand for stop in _MERCHANT_STOP):
        return None
    return cand.title()


def _clean_subject(subject: str) -> str:
    s = _RE_CLEAN_SUBJECT.sub("", (subject or "").strip()).strip()
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s[:1].upper() + s[1:]) if s else ""


def parse_email(
    subject: str,
    body: str,
    sender: str = "",
    received_date: dt.date | None = None,
) -> dict | None:
    """Extrae una transacción de un email de aviso/comprobante bancario.

    Devuelve ``{date, description, amount, currency}`` o ``None`` si el correo no
    es un movimiento (cartola, estado de cuenta, aviso de seguridad, etc.).
    """
    subj_norm = _norm(subject)
    if any(k in subj_norm for k in _SKIP):
        return None

    low = html.unescape(f"{subject}\n{body}").lower()
    amount_hit = _find_amount(low)
    if not amount_hit:
        return None
    currency, amount = amount_hit

    is_income = any(k in subj_norm for k in _INCOME_SUBJECT) or "recibiste" in low
    amount = abs(amount) if is_income else -abs(amount)

    merchant = _extract_merchant(low)
    description = (
        merchant
        or _clean_subject(subject)
        or (sender.split("@")[-1].split(".")[0].title() if sender else "")
        or "Movimiento"
    )

    fallback = received_date or dt.date.today()
    return {
        "date": _find_date(low, fallback),
        "description": description[:120],
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
