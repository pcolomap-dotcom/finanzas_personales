"""API FastAPI + servidor de la PWA."""
from __future__ import annotations

import datetime as dt
import json
from calendar import monthrange
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .bank_senders import BANK_SENDERS
from .categorize import categorize, remember
from .db import get_db, init_db
from .debts import import_debts_csv
from .email_ingest import ingest_parsed, parse_email
from .imap_sync import fetch_bank_emails
from .importers import import_file
from .models import Account, Budget, Category, Debt, Transaction
from .psd2_gocardless import (
    create_requisition,
    get_requisition,
    get_token,
    get_transactions,
    list_institutions,
)
from .psd2_mapper import map_transactions
from .transfers import suggest as suggest_transfers

app = FastAPI(title="Finanzas App", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------- helpers de serialización ---------------------------
def _f(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0


def account_dict(a: Account) -> dict:
    return {
        "id": a.id, "name": a.name, "bank": a.bank, "country": a.country,
        "currency": a.currency, "type": a.type,
    }


def category_dict(c: Category) -> dict:
    return {"id": c.id, "name": c.name, "kind": c.kind, "color": c.color, "icon": c.icon}


def tx_dict(t: Transaction) -> dict:
    return {
        "id": t.id, "account_id": t.account_id, "date": t.date.isoformat(),
        "description": t.description, "amount": _f(t.amount), "currency": t.currency,
        "category_id": t.category_id,
        "category": t.category.name if t.category else None,
        "category_icon": t.category.icon if t.category else "❓",
        "category_color": t.category.color if t.category else "#9ca3af",
        "source": t.source, "is_recurring": t.is_recurring,
        "is_internal": t.is_internal,
    }


def _month_range(month: str) -> tuple[dt.date, dt.date]:
    year, mon = (int(x) for x in month.split("-"))
    return dt.date(year, mon, 1), dt.date(year, mon, monthrange(year, mon)[1])


# --------------------------------- esquemas ------------------------------------
class AccountIn(BaseModel):
    name: str
    bank: str = ""
    country: str = "CL"
    currency: str = "CLP"
    type: str = "checking"


class CategoryPatch(BaseModel):
    category_id: int


class BudgetIn(BaseModel):
    category_id: int
    amount: float
    currency: str = "CLP"
    period: str = "monthly"


# ---------------------------------- cuentas ------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/accounts")
def list_accounts(db: Session = Depends(get_db)) -> list[dict]:
    return [account_dict(a) for a in db.query(Account).order_by(Account.name).all()]


@app.post("/api/accounts")
def create_account(payload: AccountIn, db: Session = Depends(get_db)) -> dict:
    acc = Account(**payload.model_dump())
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return account_dict(acc)


# --------------------------------- categorías ----------------------------------
@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)) -> list[dict]:
    return [category_dict(c) for c in db.query(Category).order_by(Category.kind, Category.name).all()]


# -------------------------------- transacciones --------------------------------
@app.get("/api/transactions")
def list_transactions(
    account_id: int | None = None,
    month: str | None = None,
    category_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[dict]:
    q = db.query(Transaction)
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if month:
        start, end = _month_range(month)
        q = q.filter(Transaction.date >= start, Transaction.date <= end)
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    return [tx_dict(t) for t in q.offset(offset).limit(min(limit, 1000)).all()]


@app.patch("/api/transactions/{tx_id}")
def recategorize(tx_id: int, patch: CategoryPatch, db: Session = Depends(get_db)) -> dict:
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transacción no encontrada")
    if not db.get(Category, patch.category_id):
        raise HTTPException(400, "Categoría inválida")
    tx.category_id = patch.category_id
    remember(db, tx.raw_description or tx.description, patch.category_id)  # aprende
    db.commit()
    db.refresh(tx)
    return tx_dict(tx)


# ---------------------------------- importar -----------------------------------
@app.post("/api/import/csv")
async def import_csv_endpoint(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    mapping: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Cuenta no encontrada")
    parsed_mapping = json.loads(mapping) if mapping else None
    data = await file.read()
    return import_file(db, account, data, filename=file.filename or "", mapping=parsed_mapping)


# -------------------------- ingesta desde emails -------------------------------
class EmailTextIn(BaseModel):
    account_id: int
    subject: str = ""
    body: str = ""
    sender: str = ""


class ImapSyncIn(BaseModel):
    account_id: int
    host: str
    user: str
    password: str
    sender_filter: str | None = None
    since_days: int = 30
    folder: str = "INBOX"  # p. ej. "BANCOS" si usas una etiqueta de Gmail
    use_bank_senders: bool = True  # filtra a los bancos chilenos conocidos


@app.post("/api/ingest/email/text")
def ingest_email_text(payload: EmailTextIn, db: Session = Depends(get_db)) -> dict:
    """Ingesta un email pegado a mano (útil para probar el parser)."""
    account = db.get(Account, payload.account_id)
    if not account:
        raise HTTPException(404, "Cuenta no encontrada")
    parsed = parse_email(payload.subject, payload.body, payload.sender)
    if not parsed:
        return {"imported": 0, "skipped": 0, "total": 0,
                "detail": "No se detectó un monto en el email."}
    result = ingest_parsed(db, account, [parsed])
    result["parsed"] = {**parsed, "amount": float(parsed["amount"]),
                        "date": parsed["date"].isoformat()}
    return result


@app.post("/api/ingest/email/imap")
def ingest_email_imap(payload: ImapSyncIn, db: Session = Depends(get_db)) -> dict:
    """Sincroniza avisos bancarios desde una casilla IMAP (no guarda la clave)."""
    account = db.get(Account, payload.account_id)
    if not account:
        raise HTTPException(404, "Cuenta no encontrada")
    try:
        emails = fetch_bank_emails(
            payload.host, payload.user, payload.password,
            sender_filter=payload.sender_filter, since_days=payload.since_days,
            folder=payload.folder, use_bank_senders=payload.use_bank_senders,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Error IMAP: {exc}")
    parsed = []
    banks: dict[str, int] = {}
    for e in emails:
        p = parse_email(e["subject"], e["body"], e["sender"], received_date=e["date"])
        if p:
            parsed.append(p)
            bank = e.get("bank") or "Otro"
            banks[bank] = banks.get(bank, 0) + 1
    result = ingest_parsed(db, account, parsed)
    result["emails_leidos"] = len(emails)
    result["emails_reconocidos"] = len(parsed)
    result["por_banco"] = banks
    return result


@app.get("/api/bank-senders")
def bank_senders() -> dict:
    """Catálogo de remitentes bancarios chilenos reconocidos."""
    grouped: dict[str, list[str]] = {}
    for addr, bank in BANK_SENDERS.items():
        grouped.setdefault(bank, []).append(addr)
    return {
        "count": len(BANK_SENDERS),
        "banks": [{"bank": k, "addresses": sorted(v)} for k, v in sorted(grouped.items())],
    }


@app.get("/api/bank-senders/gmail-filter")
def gmail_filter() -> dict:
    """Texto listo para crear el filtro en Gmail (etiquetar como BANCOS)."""
    query = "from:(" + " OR ".join(sorted(BANK_SENDERS)) + ")"
    return {
        "query": query,
        "label": "BANCOS",
        "pasos": [
            "Gmail → ⚙ Configuración → Ver toda la configuración → Filtros y direcciones bloqueadas",
            "Crear un filtro nuevo",
            "Pega el texto en el campo 'Incluye las palabras' (o en 'De')",
            "Crear filtro con esta búsqueda",
            "Marca 'Aplicar la etiqueta' → crea/elige la etiqueta BANCOS",
            "(Opcional) marca 'Aplicar también a X conversaciones coincidentes'",
        ],
    }


# ------------------------- open banking PSD2 (España) --------------------------
class Psd2Creds(BaseModel):
    secret_id: str
    secret_key: str
    country: str = "ES"


class Psd2Requisition(BaseModel):
    secret_id: str
    secret_key: str
    institution_id: str
    redirect: str = "http://localhost:8000/"


class Psd2Import(BaseModel):
    secret_id: str
    secret_key: str
    requisition_id: str
    account_id: int


@app.post("/api/psd2/institutions")
def psd2_institutions(creds: Psd2Creds) -> list[dict]:
    """Lista los bancos disponibles del país (para elegir el tuyo)."""
    try:
        token = get_token(creds.secret_id, creds.secret_key)
        banks = list_institutions(token, creds.country)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, str(exc))
    return [{"id": b["id"], "name": b.get("name"), "logo": b.get("logo")} for b in banks]


@app.post("/api/psd2/requisition")
def psd2_requisition(payload: Psd2Requisition) -> dict:
    """Crea el consentimiento; devuelve el link para autorizar en el banco."""
    try:
        token = get_token(payload.secret_id, payload.secret_key)
        req = create_requisition(token, payload.institution_id, payload.redirect)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, str(exc))
    return {"requisition_id": req["id"], "link": req["link"]}


@app.post("/api/psd2/import")
def psd2_import(payload: Psd2Import, db: Session = Depends(get_db)) -> dict:
    """Descarga movimientos de las cuentas autorizadas y los ingesta."""
    account = db.get(Account, payload.account_id)
    if not account:
        raise HTTPException(404, "Cuenta no encontrada")
    try:
        token = get_token(payload.secret_id, payload.secret_key)
        req = get_requisition(token, payload.requisition_id)
        parsed: list[dict] = []
        for acc_id in req.get("accounts", []):
            parsed.extend(map_transactions(get_transactions(token, acc_id)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, str(exc))
    result = ingest_parsed(db, account, parsed, source="api")
    result["cuentas_autorizadas"] = len(req.get("accounts", []))
    return result


# ------------------------------------ deudas -----------------------------------
def _next_due(payment_day: int | None, last_paid_period: str, today: dt.date) -> dt.date | None:
    """Próxima fecha de vencimiento según el día de pago y la última cuota pagada."""
    if not payment_day:
        return None

    def clamp(year: int, month: int) -> dt.date:
        return dt.date(year, month, min(payment_day, monthrange(year, month)[1]))

    cand = clamp(today.year, today.month)
    period = f"{today.year}-{today.month:02d}"
    if last_paid_period == period or cand < today:
        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        cand = clamp(year, month)
    return cand


def debt_dict(d: Debt, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    period = f"{today.year}-{today.month:02d}"
    nd = _next_due(d.payment_day, d.last_paid_period or "", today)
    return {
        "id": d.id, "institution": d.institution, "credit_type": d.credit_type,
        "current_amount": _f(d.current_amount), "original_amount": _f(d.original_amount),
        "monthly_payment": _f(d.monthly_payment), "arrears": _f(d.arrears),
        "granted_date": d.granted_date.isoformat() if d.granted_date else None,
        "due_date": d.due_date.isoformat() if d.due_date else None,
        "payment_day": d.payment_day,
        "last_paid_period": d.last_paid_period or "",
        "paid_this_month": (d.last_paid_period or "") == period,
        "next_due": nd.isoformat() if nd else None,
        "currency": d.currency,
        "is_consumo": "consumo" in (d.credit_type or "").lower(),
    }


@app.get("/api/debts")
def list_debts(db: Session = Depends(get_db)) -> dict:
    today = dt.date.today()
    period = f"{today.year}-{today.month:02d}"
    items = db.query(Debt).order_by(Debt.current_amount.desc()).all()
    total = sum(_f(d.current_amount) for d in items)
    monthly = sum(_f(d.monthly_payment) for d in items)
    consumo = sum(_f(d.current_amount) for d in items if "consumo" in (d.credit_type or "").lower())
    tarjetas = sum(_f(d.current_amount) for d in items if "tarjeta" in (d.credit_type or "").lower())
    lineas = sum(_f(d.current_amount) for d in items if "nea" in (d.credit_type or "").lower())
    arrears = sum(_f(d.arrears) for d in items)
    # Cuotas que aún vencen este mes (con día de pago y no marcadas como pagadas).
    pending = sum(
        _f(d.monthly_payment) for d in items
        if d.payment_day and (d.last_paid_period or "") != period
    )
    by_type: dict[str, float] = {}
    for d in items:
        by_type[d.credit_type or "Otro"] = by_type.get(d.credit_type or "Otro", 0.0) + _f(d.current_amount)
    return {
        "items": [debt_dict(d, today) for d in items],
        "totals": {
            "total": total, "monthly": monthly, "consumo": consumo,
            "tarjetas": tarjetas, "lineas": lineas, "arrears": arrears,
            "pending_month": pending, "count": len(items),
            "by_type": [{"type": k, "amount": v} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
        },
    }


class DebtPatch(BaseModel):
    monthly_payment: float | None = None
    payment_day: int | None = None
    current_amount: float | None = None


@app.patch("/api/debts/{debt_id}")
def update_debt(debt_id: int, patch: DebtPatch, db: Session = Depends(get_db)) -> dict:
    d = db.get(Debt, debt_id)
    if not d:
        raise HTTPException(404, "Deuda no encontrada")
    if patch.monthly_payment is not None:
        d.monthly_payment = Decimal(str(patch.monthly_payment))
    if patch.current_amount is not None:
        d.current_amount = Decimal(str(patch.current_amount))
    if patch.payment_day is not None:
        d.payment_day = patch.payment_day or None
    db.commit()
    db.refresh(d)
    return debt_dict(d)


@app.post("/api/debts/{debt_id}/mark_paid")
def mark_debt_paid(debt_id: int, period: str | None = None, db: Session = Depends(get_db)) -> dict:
    """Marca la cuota del mes indicado (o el actual) como pagada."""
    d = db.get(Debt, debt_id)
    if not d:
        raise HTTPException(404, "Deuda no encontrada")
    today = dt.date.today()
    d.last_paid_period = period or f"{today.year}-{today.month:02d}"
    db.commit()
    db.refresh(d)
    return debt_dict(d)


@app.post("/api/debts/import")
async def import_debts(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """Importa el informe de deudas CMF (CSV)."""
    data = await file.read()
    return import_debts_csv(db, data, filename=file.filename or "")


# ---------------------- traspasos internos y pagos de deuda --------------------
class ConfirmPair(BaseModel):
    id_a: int
    id_b: int


class ConfirmDebt(BaseModel):
    tx_id: int
    debt_id: int


class DismissIn(BaseModel):
    ids: list[int]


@app.get("/api/transfers/suggestions")
def transfer_suggestions(db: Session = Depends(get_db)) -> dict:
    s = suggest_transfers(db)
    pairs = [{"a": tx_dict(a), "b": tx_dict(b)} for a, b in s["pairs"]]
    payments = [
        {"tx": tx_dict(t), "kind": kind, "candidates": [debt_dict(d) for d in cands]}
        for t, kind, cands in s["debt_payments"]
    ]
    return {"pairs": pairs, "debt_payments": payments,
            "count": len(pairs) + len(payments)}


@app.post("/api/transfers/confirm_pair")
def confirm_pair(payload: ConfirmPair, db: Session = Depends(get_db)) -> dict:
    a, b = db.get(Transaction, payload.id_a), db.get(Transaction, payload.id_b)
    if not a or not b:
        raise HTTPException(404, "Transacción no encontrada")
    for t in (a, b):
        t.is_internal = True
        t.transfer_checked = True
    db.commit()
    return {"ok": True}


@app.post("/api/transfers/confirm_debt")
def confirm_debt(payload: ConfirmDebt, db: Session = Depends(get_db)) -> dict:
    t = db.get(Transaction, payload.tx_id)
    d = db.get(Debt, payload.debt_id)
    if not t or not d:
        raise HTTPException(404, "Transacción o deuda no encontrada")
    t.is_internal = True
    t.transfer_checked = True
    t.debt_id = d.id
    # El pago limpia deuda: baja el saldo (sin bajar de 0).
    d.current_amount = max(Decimal("0"), d.current_amount - abs(t.amount))
    db.commit()
    return {"ok": True, "debt_saldo": _f(d.current_amount)}


@app.post("/api/transfers/dismiss")
def dismiss_suggestions(payload: DismissIn, db: Session = Depends(get_db)) -> dict:
    for tid in payload.ids:
        t = db.get(Transaction, tid)
        if t:
            t.transfer_checked = True
    db.commit()
    return {"ok": True}


# --------------------------------- mantenimiento -------------------------------
@app.post("/api/maintenance/recategorize")
def recategorize_all(db: Session = Depends(get_db)) -> dict:
    """Re-aplica reglas y memoria a los movimientos sin categoría."""
    updated = 0
    pendientes = db.query(Transaction).filter(Transaction.category_id.is_(None)).all()
    for t in pendientes:
        cid = categorize(db, t.raw_description or t.description)
        if cid:
            t.category_id = cid
            updated += 1
    db.commit()
    return {"revisados": len(pendientes), "actualizados": updated}


# ------------------------------ salud financiera -------------------------------
def _clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


@app.get("/api/salud")
def salud(month: str | None = None, income: float | None = None,
          db: Session = Depends(get_db)) -> dict:
    """Indicador de salud financiera (base CLP): carga, ahorro, endeudamiento."""
    if not month:
        today = dt.date.today()
        month = f"{today.year}-{today.month:02d}"
    start, end = _month_range(month)
    txs = (
        db.query(Transaction)
        .filter(Transaction.date >= start, Transaction.date <= end,
                Transaction.is_internal.is_(False), Transaction.currency == "CLP")
        .all()
    )
    inc = sum(_f(t.amount) for t in txs if _f(t.amount) > 0)
    exp = sum(-_f(t.amount) for t in txs if _f(t.amount) < 0)
    debts = db.query(Debt).all()
    cuota = sum(_f(d.monthly_payment) for d in debts)
    deuda = sum(_f(d.current_amount) for d in debts)

    income_m = income if (income and income > 0) else inc
    base = {"month": month, "income": income_m, "expense": exp,
            "cuota": cuota, "deuda": deuda, "balance": income_m - exp - cuota}
    if not income_m or income_m <= 0:
        base["score"] = None
        base["message"] = "Define tu ingreso mensual para calcular tu salud financiera."
        return base

    dti = cuota / income_m
    savings = (income_m - exp - cuota) / income_m
    dti_months = deuda / income_m
    s_carga = _clamp((0.5 - dti) / (0.5 - 0.1) * 100)
    s_ahorro = _clamp(savings / 0.30 * 100)
    s_deuda = _clamp((24 - dti_months) / (24 - 3) * 100)
    score = round(0.35 * s_carga + 0.35 * s_ahorro + 0.30 * s_deuda)

    def band(sc: float) -> tuple[str, str]:
        if sc >= 80:
            return "Excelente", "#22c55e"
        if sc >= 60:
            return "Buena", "#84cc16"
        if sc >= 40:
            return "Regular", "#eab308"
        return "Delicada", "#ef4444"

    def st(sc: float) -> str:
        return "good" if sc >= 66 else "warn" if sc >= 40 else "bad"

    label, color = band(score)
    base.update({
        "score": score, "label": label, "color": color,
        "metrics": [
            {"key": "Carga financiera", "value": f"{dti * 100:.0f}%",
             "hint": "Cuota mensual de deudas sobre tu ingreso (ideal < 35%).",
             "pct": round(_clamp(dti * 100)), "status": st(s_carga)},
            {"key": "Tasa de ahorro", "value": f"{savings * 100:.0f}%",
             "hint": "Lo que te queda tras gastos y cuotas (ideal > 20%).",
             "pct": round(_clamp(savings * 100)), "status": st(s_ahorro)},
            {"key": "Endeudamiento", "value": f"{dti_months:.1f}× ingreso",
             "hint": "Meses de ingreso que equivale tu deuda total (ideal < 6).",
             "pct": round(_clamp(dti_months / 24 * 100)), "status": st(s_deuda)},
        ],
    })
    return base


# ---------------------------------- resumen ------------------------------------
@app.get("/api/summary")
def summary(month: str | None = None, db: Session = Depends(get_db)) -> dict:
    if not month:
        today = dt.date.today()
        month = f"{today.year}-{today.month:02d}"
    start, end = _month_range(month)
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.date >= start,
            Transaction.date <= end,
            Transaction.is_internal.is_(False),  # excluye traspasos internos
        )
        .all()
    )

    currencies: dict[str, dict] = {}
    for t in txs:
        cur = currencies.setdefault(
            t.currency, {"income": 0.0, "expense": 0.0, "net": 0.0, "_cats": {}}
        )
        amt = _f(t.amount)
        if amt >= 0:
            cur["income"] += amt
        else:
            cur["expense"] += -amt
            name = t.category.name if t.category else "Sin categorizar"
            slot = cur["_cats"].setdefault(
                name,
                {
                    "amount": 0.0,
                    "color": t.category.color if t.category else "#9ca3af",
                    "icon": t.category.icon if t.category else "❓",
                },
            )
            slot["amount"] += -amt
        cur["net"] += amt

    for cur in currencies.values():
        cats = [{"category": k, **v} for k, v in cur.pop("_cats").items()]
        cur["by_category"] = sorted(cats, key=lambda x: x["amount"], reverse=True)

    return {"month": month, "currencies": currencies}


# ---------------------------------- presupuestos -------------------------------
@app.get("/api/budgets")
def list_budgets(db: Session = Depends(get_db)) -> list[dict]:
    out = []
    for b in db.query(Budget).all():
        cat = db.get(Category, b.category_id)
        out.append({
            "id": b.id, "category_id": b.category_id,
            "category": cat.name if cat else None,
            "amount": _f(b.amount), "currency": b.currency, "period": b.period,
        })
    return out


@app.post("/api/budgets")
def create_budget(payload: BudgetIn, db: Session = Depends(get_db)) -> dict:
    b = Budget(
        category_id=payload.category_id, amount=Decimal(str(payload.amount)),
        currency=payload.currency, period=payload.period,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return {"id": b.id, "category_id": b.category_id, "amount": _f(b.amount), "currency": b.currency}


@app.get("/api/budgets/status")
def budgets_status(month: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    if not month:
        today = dt.date.today()
        month = f"{today.year}-{today.month:02d}"
    start, end = _month_range(month)
    out = []
    for b in db.query(Budget).all():
        cat = db.get(Category, b.category_id)
        spent = 0.0
        for t in (
            db.query(Transaction)
            .filter(
                Transaction.category_id == b.category_id,
                Transaction.currency == b.currency,
                Transaction.date >= start,
                Transaction.date <= end,
                Transaction.amount < 0,
            )
            .all()
        ):
            spent += -_f(t.amount)
        limit = _f(b.amount)
        out.append({
            "budget_id": b.id,
            "category": cat.name if cat else None,
            "icon": cat.icon if cat else "💸",
            "color": cat.color if cat else "#888",
            "limit": limit, "spent": spent, "currency": b.currency,
            "pct": round(spent / limit * 100, 1) if limit else 0,
        })
    return out


# ------------------------- PWA (estáticos, al final) ---------------------------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
