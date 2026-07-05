# Conexión automática de cuentas

Dos vías gratuitas, según país. Ninguna guarda tus credenciales bancarias.

## 🇨🇱 Chile — Emails de aviso bancario (modelo Kuanto)

Chile no tiene open banking operativo hasta 2026 (Ley Fintech / SFA-CMF, Etapa 1
en julio 2026). La vía gratuita es leer los **correos de aviso de compra** que
envían los bancos y convertirlos en transacciones.

### Opción A — Pegar un email (para probar)
`POST /api/ingest/email/text`
```json
{ "account_id": 1, "subject": "Aviso de compra",
  "body": "Compra por $12.990 en LIDER el 03/07/2026 ...",
  "sender": "enviodigital@bancochile.cl" }
```

### Opción B — Sincronizar tu casilla por IMAP (automático)
1. En Gmail/Outlook crea una **contraseña de aplicación**.
2. (Opcional) crea una regla que etiquete los avisos del banco.
3. Llama `POST /api/ingest/email/imap`:
```json
{ "account_id": 1, "host": "imap.gmail.com", "user": "tucorreo@gmail.com",
  "password": "APP_PASSWORD", "sender_filter": "bancochile.cl", "since_days": 30 }
```
La app lee en modo solo-lectura, parsea y agrega las transacciones (con dedup).

**Bancos probados en el parser**: Banco de Chile, Santander, BCI, Mach, Falabella
(patrones genéricos; se extienden fácil en `app/email_ingest.py`).

## 🇪🇸 España — Open Banking PSD2 (GoCardless / Nordigen, free tier)

Solo-lectura, regulado (AISP). Tú autorizas en la web de tu banco.

1. Crea cuenta gratis en <https://bankaccountdata.gocardless.com/> y genera
   `secret_id` y `secret_key`.
2. Lista bancos: `POST /api/psd2/institutions` `{secret_id, secret_key, country:"ES"}`.
3. Crea consentimiento: `POST /api/psd2/requisition` `{..., institution_id}` →
   abre el `link` y autoriza en tu banco.
4. Importa movimientos: `POST /api/psd2/import` `{..., requisition_id, account_id}`.

## Roadmap
- CL: migrar a las APIs del **SFA** cuando estén disponibles (2026+); alternativa
  **Fintoc** (gratis hasta 5 cuentas de persona natural).
- Añadir UI para estos flujos (hoy están en la API; el MVP web cubre el import CSV).
