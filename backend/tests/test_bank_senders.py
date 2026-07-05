"""Pruebas del catálogo de remitentes bancarios.

Ejecutar:  python tests/test_bank_senders.py   (desde backend/)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.bank_senders import (  # noqa: E402
    BANK_SENDERS, bank_for_sender, gmail_from_query, is_bank_sender,
)

CHECKS = [
    ("From con nombre", bank_for_sender("Banco de Chile <enviodigital@bancochile.cl>") == "Banco de Chile"),
    ("dirección directa", bank_for_sender("mensajeria@santander.cl") == "Banco Santander"),
    ("eeccvirtual Itaú", bank_for_sender("itau@eeccvirtual.cl") == "Itaú"),
    ("Mercado Pago", bank_for_sender("info@mercadopago.com") == "Mercado Pago"),
    ("desconocido → None", bank_for_sender("amigo@gmail.com") is None),
    ("is_bank_sender", is_bank_sender("no-reply@tenpo.cl") is True),
    ("por dominio", bank_for_sender("otracosa@bancochile.cl") == "Banco de Chile"),
    ("catálogo ≥ 60", len(BANK_SENDERS) >= 60),
    ("gmail query formato", "from:(" in gmail_from_query(15) and "newer_than:15d" in gmail_from_query(15)),
    ("gmail query incluye banco", "enviodigital@bancochile.cl" in gmail_from_query()),
]


def run() -> int:
    failures = 0
    for name, ok in CHECKS:
        print(f"  {'✓' if ok else '✗'} {name}")
        failures += 0 if ok else 1
    print(f"\n{'TODO OK ✅' if failures == 0 else f'{failures} FALLO(S) ❌'}  "
          f"({len(BANK_SENDERS)} remitentes en catálogo)")
    return failures


def test_bank_senders():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
