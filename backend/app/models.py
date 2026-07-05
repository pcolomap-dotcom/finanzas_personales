"""Modelo de datos de la app de finanzas."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    bank: Mapped[str] = mapped_column(String(80), default="")
    country: Mapped[str] = mapped_column(String(2), default="CL")  # CL | ES
    currency: Mapped[str] = mapped_column(String(3), default="CLP")  # CLP | EUR
    type: Mapped[str] = mapped_column(String(30), default="checking")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="expense")  # expense|income|transfer
    color: Mapped[str] = mapped_column(String(9), default="#888888")
    icon: Mapped[str] = mapped_column(String(8), default="💸")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    raw_description: Mapped[str] = mapped_column(String(300), default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # + ingreso / - gasto
    currency: Mapped[str] = mapped_column(String(3), default="CLP")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)  # traspaso interno (excluido del resumen)
    transfer_checked: Mapped[bool] = mapped_column(Boolean, default=False)  # ya revisado (no re-sugerir)
    debt_id: Mapped[int | None] = mapped_column(ForeignKey("debts.id"), nullable=True)  # pago aplicado a deuda
    source: Mapped[str] = mapped_column(String(10), default="csv")  # csv|pdf|email|api|manual
    dedup_hash: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped["Account"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship()


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(120))
    match_type: Mapped[str] = mapped_column(String(10), default="contains")  # contains|regex
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    priority: Mapped[int] = mapped_column(Integer, default=100)


class MerchantMemory(Base):
    """Aprende la categoría corregida por el usuario para un comercio."""

    __tablename__ = "merchant_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_merchant: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CLP")
    period: Mapped[str] = mapped_column(String(10), default="monthly")


class Debt(Base):
    """Operación de crédito vigente (importada del informe de deudas CMF/BIC)."""

    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution: Mapped[str] = mapped_column(String(120))
    credit_type: Mapped[str] = mapped_column(String(60), default="")  # Consumo|Tarjeta|Línea
    code: Mapped[str] = mapped_column(String(80), default="", index=True)  # código operación
    original_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    at_day_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    monthly_payment: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)  # carga financiera
    arrears: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)  # mora actual
    granted_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    report_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    payment_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # día de vencimiento mensual
    last_paid_period: Mapped[str] = mapped_column(String(7), default="")  # "YYYY-MM" cuota ya pagada
    currency: Mapped[str] = mapped_column(String(3), default="CLP")
    source: Mapped[str] = mapped_column(String(10), default="cmf")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    filename: Mapped[str] = mapped_column(String(200), default="")
    imported_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    count: Mapped[int] = mapped_column(Integer, default=0)
