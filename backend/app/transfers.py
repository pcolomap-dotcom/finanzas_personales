"""Detección de traspasos internos y pagos de deuda (para sugerir al usuario).

- Traspaso interno: una salida en una cuenta y una entrada del MISMO monto en otra
  cuenta, con fechas cercanas. Se sugiere y, tras tu aprobación, se excluye del
  resumen de gastos/ingresos.
- Pago de deuda: un cargo cuya glosa indica pago de tarjeta/línea/crédito. Se sugiere
  aplicarlo a la deuda correspondiente; al aprobar, baja el saldo de esa deuda.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from .categorize import normalize
from .models import Debt, Transaction

_PAY_KEYWORDS = (
    "pago tarjeta", "pago de tarjeta", "pago tc", "pago linea", "pago de credito",
    "pago deuda", "pago cuotas", "pago de tarjeta de credito", "pago linea de cred",
    "pat tarjeta", "pago beneficiario",
)


def _debt_type(desc_norm: str) -> str:
    if "tarjeta" in desc_norm or " tc" in desc_norm or "tcr" in desc_norm:
        return "tarjeta"
    if "linea" in desc_norm:
        return "linea"
    return "consumo"


def _matches_debt(debt: Debt, kind: str) -> bool:
    ct = normalize(debt.credit_type)
    if kind == "tarjeta":
        return "tarjeta" in ct
    if kind == "linea":
        return "linea" in ct
    return "consumo" in ct or "credito" in ct


def suggest(db: Session, max_days: int = 4) -> dict:
    """Devuelve sugerencias de traspasos internos y pagos de deuda."""
    pending = (
        db.query(Transaction)
        .filter(Transaction.is_internal.is_(False), Transaction.transfer_checked.is_(False))
        .all()
    )
    debts = db.query(Debt).all()

    # --- pares de traspaso interno (misma magnitud, cuentas distintas) ---
    negs = [t for t in pending if float(t.amount) < 0]
    poss = [t for t in pending if float(t.amount) > 0]
    used: set[int] = set()
    pairs = []
    for a in sorted(negs, key=lambda t: t.date):
        for b in poss:
            if b.id in used or a.id in used:
                continue
            if a.account_id == b.account_id:
                continue
            if abs(float(a.amount)) != abs(float(b.amount)):
                continue
            if abs((a.date - b.date).days) > max_days:
                continue
            used.add(a.id)
            used.add(b.id)
            pairs.append((a, b))
            break

    # --- pagos de deuda (glosa de pago + deuda del tipo correspondiente) ---
    debt_payments = []
    for t in pending:
        if float(t.amount) >= 0 or t.id in used:
            continue
        dn = normalize(t.description)
        if not any(k in dn for k in _PAY_KEYWORDS):
            continue
        kind = _debt_type(dn)
        candidates = [d for d in debts if _matches_debt(d, kind)]
        if candidates:
            debt_payments.append((t, kind, candidates))

    return {"pairs": pairs, "debt_payments": debt_payments}
