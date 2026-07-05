"""Convierte la respuesta de transacciones de GoCardless a nuestro formato."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation


def map_transactions(payload: dict) -> list[dict]:
    """De la respuesta `/accounts/{id}/transactions/` a lista de dicts parseados.

    Cada item: ``{date, description, amount, currency}`` con el signo tal como lo
    entrega el banco (gasto negativo, ingreso positivo).
    """
    booked = (payload.get("transactions") or {}).get("booked", [])
    out: list[dict] = []
    for t in booked:
        amt = t.get("transactionAmount") or {}
        try:
            amount = Decimal(str(amt.get("amount", "0")))
        except InvalidOperation:
            continue
        if amount == 0:
            continue

        raw_date = t.get("bookingDate") or t.get("valueDate")
        try:
            date = dt.date.fromisoformat(raw_date[:10]) if raw_date else dt.date.today()
        except (ValueError, TypeError):
            date = dt.date.today()

        desc = (
            t.get("remittanceInformationUnstructured")
            or t.get("creditorName")
            or t.get("debtorName")
            or "Movimiento"
        ).strip()

        out.append({
            "date": date,
            "description": desc[:120],
            "amount": amount,
            "currency": amt.get("currency", "EUR"),
        })
    return out
