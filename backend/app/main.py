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

from .categorize import remember
from .db import get_db, init_db
from .email_ingest import ingest_parsed, parse_email
from .imap_sync import fetch_bank_emails
from .importers import import_csv
from .models import Account, Budget, Category, Transaction
from .psd2_gocardless import (
    create_requisition,
    get_requisition,
    get_token,
    get_transactions,
    list_institutions,
)
from .psd2_mapper import map_transactions

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
    return import_csv(db, account, data, filename=file.filename or "", mapping=parsed_mapping)


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
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Error IMAP: {exc}")
    parsed = []
    for e in emails:
        p = parse_email(e["subject"], e["body"], e["sender"], received_date=e["date"])
        if p:
            parsed.append(p)
    result = ingest_parsed(db, account, parsed)
    result["emails_leidos"] = len(emails)
    result["emails_reconocidos"] = len(parsed)
    return result


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


# ---------------------------------- resumen ------------------------------------
@app.get("/api/summary")
def summary(month: str | None = None, db: Session = Depends(get_db)) -> dict:
    if not month:
        today = dt.date.today()
        month = f"{today.year}-{today.month:02d}"
    start, end = _month_range(month)
    txs = (
        db.query(Transaction)
        .filter(Transaction.date >= start, Transaction.date <= end)
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
