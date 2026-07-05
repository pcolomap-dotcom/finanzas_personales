"""Pruebas del parser de emails de aviso bancario (CL + ES).

Ejecutar:  python tests/test_email_parser.py   (desde backend/)
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.email_ingest import parse_email  # noqa: E402

CASES = [
    {
        "name": "Banco de Chile - compra",
        "subject": "Aviso de compra",
        "body": "Te informamos que se realizó una compra por $12.990 en LIDER "
                "el 03/07/2026 con tu tarjeta terminada en 1234.",
        "sender": "enviodigital@bancochile.cl",
        "expect": {"amount": -12990, "currency": "CLP", "merchant": "LIDER",
                   "date": dt.date(2026, 7, 3)},
    },
    {
        "name": "Santander - tarjeta de crédito",
        "subject": "Compra con tu tarjeta",
        "body": "Compra por $45.500 en FALABELLA con Tarjeta de Crédito el 04/07/2026.",
        "sender": "avisos@santander.cl",
        "expect": {"amount": -45500, "currency": "CLP", "merchant": "FALABELLA",
                   "date": dt.date(2026, 7, 4)},
    },
    {
        "name": "BCI - compra",
        "subject": "Notificación BCI",
        "body": "Realizaste una compra por $8.900 en UBER RIDES el 05-07-2026.",
        "sender": "notificaciones@bci.cl",
        "expect": {"amount": -8900, "currency": "CLP", "merchant": "UBER RIDES",
                   "date": dt.date(2026, 7, 5)},
    },
    {
        "name": "Mach - sin fecha (usa received_date)",
        "subject": "Compra Mach",
        "body": "Compraste $5.100 en SPOTIFY.",
        "sender": "hola@mach.cl",
        "received_date": dt.date(2026, 7, 6),
        "expect": {"amount": -5100, "currency": "CLP", "merchant": "SPOTIFY",
                   "date": dt.date(2026, 7, 6)},
    },
    {
        "name": "Abono / ingreso",
        "subject": "Abono en tu cuenta",
        "body": "Recibiste un abono por transferencia de $150.000 el 06/07/2026.",
        "sender": "avisos@santander.cl",
        "expect": {"amount": 150000, "currency": "CLP", "date": dt.date(2026, 7, 6)},
    },
    {
        "name": "BBVA España - EUR",
        "subject": "Notificación de compra BBVA",
        "body": "Has realizado una compra de 64,35 € en MERCADONA el 01/07/2026.",
        "sender": "notificaciones@bbva.es",
        "expect": {"amount": -64.35, "currency": "EUR", "merchant": "MERCADONA",
                   "date": dt.date(2026, 7, 1)},
    },
    {
        "name": "Itaú - tarjeta de crédito",
        "subject": "Aviso de compra Itaú",
        "body": "Compra por $23.990 en JUMBO con tu Tarjeta de Crédito el 15/06/2026.",
        "sender": "itaupersonas@itau.cl",
        "expect": {"amount": -23990, "currency": "CLP", "merchant": "JUMBO",
                   "date": dt.date(2026, 6, 15)},
    },
    {
        "name": "Mercado Pago - sin fecha",
        "subject": "Pago realizado",
        "body": "Pagaste $5.990 en SPOTIFY con Mercado Pago.",
        "sender": "info@mercadopago.com",
        "received_date": dt.date(2026, 6, 20),
        "expect": {"amount": -5990, "currency": "CLP", "merchant": "SPOTIFY",
                   "date": dt.date(2026, 6, 20)},
    },
    {
        "name": "BancoEstado - compra",
        "subject": "Compra con tu tarjeta",
        "body": "Compra por $8.500 en COPEC el 10/06/2026.",
        "sender": "notificaciones@correo.bancoestado.cl",
        "expect": {"amount": -8500, "currency": "CLP", "merchant": "COPEC",
                   "date": dt.date(2026, 6, 10)},
    },
]


def run() -> int:
    failures = 0
    for c in CASES:
        got = parse_email(c["subject"], c["body"], c["sender"], c.get("received_date"))
        exp = c["expect"]
        ok = True
        reasons = []
        if got is None:
            ok = False
            reasons.append("parser devolvió None")
        else:
            if abs(float(got["amount"]) - exp["amount"]) > 0.001:
                ok = False; reasons.append(f"amount {got['amount']} != {exp['amount']}")
            if got["currency"] != exp["currency"]:
                ok = False; reasons.append(f"currency {got['currency']} != {exp['currency']}")
            if "merchant" in exp and exp["merchant"] not in got["description"].upper():
                ok = False; reasons.append(f"merchant '{exp['merchant']}' no en '{got['description']}'")
            if got["date"] != exp["date"]:
                ok = False; reasons.append(f"date {got['date']} != {exp['date']}")
        status = "✓" if ok else "✗"
        detail = "" if ok else "  →  " + "; ".join(reasons)
        extra = f"  [{got['description']} | {got['amount']} {got['currency']} | {got['date']}]" if got else ""
        print(f"  {status} {c['name']}{extra}{detail}")
        failures += 0 if ok else 1
    print(f"\n{'TODO OK ✅' if failures == 0 else f'{failures} FALLO(S) ❌'}  ({len(CASES)} casos)")
    return failures


# Compatibilidad con pytest
def test_all_cases():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
