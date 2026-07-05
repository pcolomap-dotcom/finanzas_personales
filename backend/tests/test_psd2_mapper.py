"""Prueba del mapper PSD2 (GoCardless) con un payload de ejemplo.

Ejecutar:  python tests/test_psd2_mapper.py   (desde backend/)
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.psd2_mapper import map_transactions  # noqa: E402

SAMPLE = {
    "transactions": {
        "booked": [
            {"bookingDate": "2026-07-01",
             "transactionAmount": {"amount": "-64.35", "currency": "EUR"},
             "remittanceInformationUnstructured": "MERCADONA VALENCIA"},
            {"bookingDate": "2026-07-02",
             "transactionAmount": {"amount": "2100.00", "currency": "EUR"},
             "remittanceInformationUnstructured": "NOMINA EMPRESA SL"},
            {"valueDate": "2026-07-03",
             "transactionAmount": {"amount": "-13.99", "currency": "EUR"},
             "creditorName": "NETFLIX SPAIN"},
            {"bookingDate": "2026-07-04",
             "transactionAmount": {"amount": "0", "currency": "EUR"},
             "remittanceInformationUnstructured": "SALDO"},
        ],
        "pending": [],
    }
}


def run() -> int:
    txs = map_transactions(SAMPLE)
    failures = 0

    def check(cond, msg):
        nonlocal failures
        print(f"  {'✓' if cond else '✗'} {msg}")
        if not cond:
            failures += 1

    check(len(txs) == 3, f"3 transacciones mapeadas (monto 0 descartado) → {len(txs)}")
    if len(txs) == 3:
        check(float(txs[0]["amount"]) == -64.35 and txs[0]["currency"] == "EUR",
              f"gasto Mercadona -64.35 EUR → {txs[0]['amount']}")
        check("MERCADONA" in txs[0]["description"], "glosa desde remittanceInformation")
        check(txs[0]["date"] == dt.date(2026, 7, 1), "fecha desde bookingDate")
        check(float(txs[1]["amount"]) == 2100.0, "ingreso nómina +2100")
        check(txs[2]["date"] == dt.date(2026, 7, 3) and "NETFLIX" in txs[2]["description"],
              "fallback a valueDate y creditorName")
    print(f"\n{'TODO OK ✅' if failures == 0 else f'{failures} FALLO(S) ❌'}")
    return failures


def test_mapper():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
