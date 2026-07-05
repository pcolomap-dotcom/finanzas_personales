"""Cliente PSD2 para España vía GoCardless Bank Account Data (ex-Nordigen).

Free tier apto para uso personal. Solo-lectura y regulado (AISP). El usuario
autoriza en la web de su banco; nosotros nunca vemos sus credenciales.

Cómo obtener claves gratis:
  1. Crea cuenta en https://bankaccountdata.gocardless.com/
  2. En "User Secrets" genera `secret_id` y `secret_key`.
  3. Úsalas en los endpoints /api/psd2/*.

Flujo:
  token = get_token(id, key)
  institutions = list_institutions(token, "ES")          # elige tu banco
  req = create_requisition(token, institution_id)         # abre req["link"]
  # ...el usuario autoriza en el banco...
  accounts = get_requisition(token, req["id"])["accounts"]
  data = get_transactions(token, accounts[0])             # movimientos
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

BASE = "https://bankaccountdata.gocardless.com/api/v2"


def _request(method: str, path: str, token: str | None = None, data: dict | None = None) -> dict:
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GoCardless HTTP {exc.code}: {detail}") from exc


def get_token(secret_id: str, secret_key: str) -> str:
    resp = _request("POST", "/token/new/", data={"secret_id": secret_id, "secret_key": secret_key})
    return resp["access"]


def list_institutions(token: str, country: str = "ES") -> list[dict]:
    return _request("GET", f"/institutions/?country={country}", token=token)


def create_requisition(token: str, institution_id: str,
                       redirect: str = "http://localhost:8000/") -> dict:
    return _request("POST", "/requisitions/", token=token, data={
        "redirect": redirect, "institution_id": institution_id,
        "reference": uuid.uuid4().hex, "user_language": "ES",
    })


def get_requisition(token: str, requisition_id: str) -> dict:
    return _request("GET", f"/requisitions/{requisition_id}/", token=token)


def get_transactions(token: str, account_id: str) -> dict:
    return _request("GET", f"/accounts/{account_id}/transactions/", token=token)
