"""Configuración de la base de datos SQLite local."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "finanzas.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base declarativa para los modelos ORM."""


def get_db():
    """Dependencia FastAPI: entrega una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea las tablas si no existen y aplica micro-migraciones."""
    from . import models  # noqa: F401  (registra los modelos)

    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate() -> None:
    """Añade columnas nuevas a tablas existentes (SQLite ADD COLUMN idempotente)."""
    from sqlalchemy import text

    wanted = {
        "debts": [
            ("payment_day", "INTEGER"),
            ("last_paid_period", "VARCHAR(7) DEFAULT ''"),
        ],
        "transactions": [
            ("is_internal", "BOOLEAN DEFAULT 0"),
            ("transfer_checked", "BOOLEAN DEFAULT 0"),
            ("debt_id", "INTEGER"),
        ],
    }
    with engine.begin() as conn:
        for table, columns in wanted.items():
            info = list(conn.execute(text(f"PRAGMA table_info({table})")))
            if not info:
                continue  # la tabla aún no existe; create_all ya la crea completa
            existing = {row[1] for row in info}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
