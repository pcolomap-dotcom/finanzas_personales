"""Importador de cartolas CSV (formatos chilenos y españoles)."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from .categorize import categorize, normalize
from .models import Account, ImportBatch, Transaction

# Palabras clave para autodetectar columnas por cabecera.
_DATE_COLS = ["fecha", "date", "fecha transaccion", "fecha operacion", "f operacion"]
_DESC_COLS = [
    "descripcion", "glosa", "detalle", "concepto", "comercio", "movimiento",
    "description", "referencia",
]
_AMOUNT_COLS = ["monto", "importe", "amount", "valor", "cargo abono"]
_DEBIT_COLS = ["cargo", "debito", "debe", "gasto", "cargos"]
_CREDIT_COLS = ["abono", "credito", "haber", "deposito", "ingreso", "abonos"]

_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y",
    "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d",
)


def parse_amount(raw: str | None) -> Decimal:
    """Interpreta montos en formato chileno (1.234) o español (1.234,56)."""
    if raw is None:
        return Decimal("0")
    s = str(raw).strip()
    if not s:
        return Decimal("0")

    neg = False
    if s.startswith("(") and s.endswith(")"):  # notación contable
        neg = True

    # Limpieza: conservar sólo dígitos y separadores.
    cleaned = "".join(ch for ch in s if ch.isdigit() or ch in ",.-")
    if cleaned.startswith("-") or (raw.strip().startswith("-")):
        neg = True
    cleaned = cleaned.replace("-", "")
    if not cleaned:
        return Decimal("0")

    has_dot = "." in cleaned
    has_comma = "," in cleaned
    if has_dot and has_comma:
        # El separador que aparece más a la derecha es el decimal.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        dec = cleaned.split(",")[-1]
        cleaned = cleaned.replace(",", ".") if len(dec) in (1, 2) else cleaned.replace(",", "")
    elif has_dot:
        dec = cleaned.split(".")[-1]
        if len(dec) not in (1, 2):  # el punto es separador de miles
            cleaned = cleaned.replace(".", "")

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")
    return -value if neg else value


def parse_date(raw: str | None) -> dt.date | None:
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def dedup_hash(account_id: int, date: dt.date, amount: Decimal, raw: str) -> str:
    key = f"{account_id}|{date.isoformat()}|{amount}|{normalize(raw)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _detect_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        return ";" if sample.count(";") >= sample.count(",") else ","


def insert_transaction(
    db: Session,
    account: Account,
    date: dt.date,
    description: str,
    amount: Decimal,
    source: str = "csv",
    currency: str | None = None,
) -> Transaction | None:
    """Inserta una transacción categorizada, evitando duplicados.

    Devuelve la transacción creada, o ``None`` si es duplicada o monto cero.
    Reutilizada por el import CSV y por la ingesta de emails.
    """
    if amount == 0:
        return None
    dhash = dedup_hash(account.id, date, amount, description)
    if db.query(Transaction.id).filter(Transaction.dedup_hash == dhash).first():
        return None
    tx = Transaction(
        account_id=account.id,
        date=date,
        description=description,
        raw_description=description,
        amount=amount,
        currency=currency or account.currency,
        category_id=categorize(db, description),
        source=source,
        dedup_hash=dhash,
    )
    db.add(tx)
    return tx


def _find_col(headers: list[str], candidates: list[str]) -> str | None:
    norm_map = {normalize(h): h for h in headers}
    for cand in candidates:
        ncand = normalize(cand)
        for nh, original in norm_map.items():
            if ncand == nh or (ncand and ncand in nh):
                return original
    return None


def import_csv(
    db: Session,
    account: Account,
    data: bytes,
    filename: str = "",
    mapping: dict | None = None,
) -> dict:
    """Importa un CSV a la cuenta dada. Devuelve un resumen del proceso."""
    text = _decode(data)
    delimiter = (mapping or {}).get("delimiter") or _detect_delimiter(text[:4096])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    if not headers:
        return {"error": "No se detectaron columnas en el archivo.", "imported": 0}

    mapping = mapping or {}
    date_col = mapping.get("date_col") or _find_col(headers, _DATE_COLS)
    desc_col = mapping.get("desc_col") or _find_col(headers, _DESC_COLS)
    amount_col = mapping.get("amount_col") or _find_col(headers, _AMOUNT_COLS)
    debit_col = mapping.get("debit_col") or _find_col(headers, _DEBIT_COLS)
    credit_col = mapping.get("credit_col") or _find_col(headers, _CREDIT_COLS)

    if not date_col or not desc_col or not (amount_col or debit_col or credit_col):
        return {
            "error": "No se pudieron mapear columnas (fecha/descripción/monto).",
            "headers": headers,
            "imported": 0,
        }

    imported = skipped = 0
    for row in reader:
        date = parse_date(row.get(date_col))
        desc = (row.get(desc_col) or "").strip()
        if not date or not desc:
            skipped += 1
            continue

        if amount_col:
            amount = parse_amount(row.get(amount_col))
        else:
            debit = parse_amount(row.get(debit_col)) if debit_col else Decimal("0")
            credit = parse_amount(row.get(credit_col)) if credit_col else Decimal("0")
            amount = abs(credit) - abs(debit)  # ingreso positivo, gasto negativo

        if amount == 0:
            skipped += 1
            continue

        if insert_transaction(db, account, date, desc, amount, source="csv") is None:
            skipped += 1
            continue
        imported += 1

    if imported:
        db.add(ImportBatch(account_id=account.id, filename=filename, count=imported))
    db.commit()
    return {"imported": imported, "skipped": skipped, "total": imported + skipped}
