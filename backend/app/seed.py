"""Crea la BD y carga categorías y reglas por defecto (comercios CL + ES)."""
from __future__ import annotations

from .db import SessionLocal, init_db
from .models import Account, Category, Rule

# (nombre, kind, color, icono)
CATEGORIES = [
    ("Sin categorizar", "expense", "#9ca3af", "❓"),
    ("Supermercado", "expense", "#22c55e", "🛒"),
    ("Restaurantes", "expense", "#f97316", "🍽️"),
    ("Transporte", "expense", "#0ea5e9", "🚌"),
    ("Combustible", "expense", "#ef4444", "⛽"),
    ("Servicios básicos", "expense", "#6366f1", "💡"),
    ("Salud", "expense", "#ec4899", "💊"),
    ("Seguros", "expense", "#0891b2", "🛡️"),
    ("Educación", "expense", "#14b8a6", "📚"),
    ("Entretenimiento", "expense", "#a855f7", "🎬"),
    ("Suscripciones", "expense", "#8b5cf6", "🔁"),
    ("Compras", "expense", "#eab308", "🛍️"),
    ("Hogar", "expense", "#84cc16", "🏠"),
    ("Viajes", "expense", "#06b6d4", "✈️"),
    ("Comisiones bancarias", "expense", "#dc2626", "🏦"),
    ("Retiros efectivo", "expense", "#78716c", "🏧"),
    ("Impuestos", "expense", "#b91c1c", "🧾"),
    ("Otros gastos", "expense", "#6b7280", "💸"),
    ("Sueldo", "income", "#16a34a", "💰"),
    ("Transferencias recibidas", "income", "#10b981", "📥"),
    ("Reembolsos", "income", "#34d399", "↩️"),
    ("Otros ingresos", "income", "#059669", "➕"),
    ("Transferencias", "transfer", "#64748b", "🔀"),
    ("Pago tarjeta", "transfer", "#475569", "💳"),
]

# categoría -> palabras clave (contains)
RULES: dict[str, list[str]] = {
    "Supermercado": ["lider", "jumbo", "santa isabel", "unimarc", "tottus", "acuenta",
                      "mercadona", "carrefour", "supermercado", "supercor", "consum", "alcampo"],
    "Restaurantes": ["mcdonald", "burger", "starbucks", "uber eats", "rappi", "pedidosya",
                     "restaurant", "doggis", "glovo", "just eat", "telepizza", "kfc", "subway",
                     "five guys", "goiko", "gelateria", "cerveceria", "taberna", "xarcuteria"],
    "Transporte": ["uber", "cabify", "didi", "metro", "transantiago", "red movilidad", "bip",
                   "taxi", "renfe", "cercanias", "emt", "peaje", "autopista", "ouigo", "ave ",
                   "alsa", "bus"],
    "Entretenimiento": ["museo", "cine", "teatro", "entrada", "cinepolis", "cinemark"],
    "Combustible": ["copec", "shell", "petrobras", "aramco", "repsol", "cepsa", "bencina",
                    "combustible", "gasolinera", "esso", "terpel"],
    "Servicios básicos": ["enel", "cge", "aguas andinas", "metrogas", "movistar", "entel",
                          "wom", "vtr", "iberdrola", "naturgy", "endesa", "vodafone", "orange",
                          "jazztel", "agua", "gasgas"],
    "Salud": ["farmacia", "cruz verde", "salcobrand", "ahumada", "clinica", "isapre", "fonasa",
              "sanitas", "adeslas", "hospital", "consulta"],
    "Seguros": ["seguro", "prima seguro", "desgravamen", "seguro 360"],
    "Educación": ["colegio", "universidad", "matricula", "curso", "udemy", "coursera"],
    "Suscripciones": ["netflix", "spotify", "disney", "hbo", "max ", "amazon prime", "youtube",
                      "apple com", "icloud", "chatgpt", "openai", "dropbox", "canva", "notion",
                      "google play", "youtu", "merpago", "mercpago", "prime video"],
    "Compras": ["falabella", "paris", "ripley", "amazon", "aliexpress", "mercadolibre",
                "mercado libre", "zara", "decathlon", "pccomponentes", "el corte ingles", "ikea",
                "primark", "stradivarius", "bershka", "pull and bear", "coolligan"],
    "Comisiones bancarias": ["comision", "mantencion", "mantenimiento", "interes", "cargo mensual"],
    "Retiros efectivo": ["giro", "cajero", "atm", "retiro efectivo", "reintegro"],
    "Impuestos": ["sii", "tesoreria", "impuesto", "agencia tributaria", "hacienda", "patente"],
    "Sueldo": ["sueldo", "remuneracion", "nomina", "salario", "haberes", "abono nomina"],
    "Reembolsos": ["devolucion", "reembolso", "reverso", "abono devolucion"],
    "Transferencias recibidas": ["abono transferencia", "transferencia recibida", "bizum recibido"],
    "Transferencias": ["transferencia", "traspaso", "transf ", "bizum", "pago a"],
    "Pago tarjeta": ["pago tarjeta", "pago tc", "pat tarjeta", "pago de tarjeta",
                     "pago linea de cred", "linea de cred", "tarjeta cmr", "cargo por pago tc"],
}

DEMO_ACCOUNTS = [
    ("Cuenta Corriente Chile", "Banco de Chile", "CL", "CLP", "checking"),
    ("Cuenta Nómina España", "BBVA", "ES", "EUR", "checking"),
]


def run(with_demo_accounts: bool = True) -> None:
    """Crea la BD y agrega categorías/reglas que falten (idempotente).

    Se puede re-ejecutar sin duplicar: solo añade lo nuevo. Útil tras una
    actualización que trae reglas nuevas.
    """
    init_db()
    db = SessionLocal()
    try:
        existing_cats = {c.name for c in db.query(Category).all()}
        added_c = 0
        for name, kind, color, icon in CATEGORIES:
            if name not in existing_cats:
                db.add(Category(name=name, kind=kind, color=color, icon=icon))
                added_c += 1
        db.commit()

        by_name = {c.name: c.id for c in db.query(Category).all()}
        existing_rules = {(r.pattern, r.category_id) for r in db.query(Rule).all()}
        added_r = 0
        for cat_name, patterns in RULES.items():
            cid = by_name.get(cat_name)
            if not cid:
                continue
            for i, pat in enumerate(patterns):
                if (pat, cid) not in existing_rules:
                    db.add(Rule(pattern=pat, match_type="contains", category_id=cid, priority=100 + i))
                    added_r += 1
        db.commit()

        if with_demo_accounts and db.query(Account).count() == 0:
            for name, bank, country, currency, atype in DEMO_ACCOUNTS:
                db.add(Account(name=name, bank=bank, country=country, currency=currency, type=atype))
            db.commit()
            print(f"✓ {len(DEMO_ACCOUNTS)} cuentas de ejemplo creadas")

        print(f"✓ Categorías: {len(by_name)} (nuevas: {added_c}) · Reglas nuevas: {added_r}")
        print("Base de datos lista.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
