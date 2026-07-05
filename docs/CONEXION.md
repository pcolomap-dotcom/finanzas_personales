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

### Opción B — Sincronizar tu casilla por IMAP (automático, modelo Kuanto)
1. En Gmail/Outlook crea una **contraseña de aplicación**.
2. Llama `POST /api/ingest/email/imap` con `use_bank_senders: true`:
```json
{ "account_id": 1, "host": "imap.gmail.com", "user": "tucorreo@gmail.com",
  "password": "APP_PASSWORD", "since_days": 30, "use_bank_senders": true }
```
Con `use_bank_senders` el app **filtra solo los correos de bancos chilenos conocidos**
(no necesitas indicar el remitente). En Gmail usa la búsqueda nativa
`from:(... OR ...) newer_than:Nd`; en otros proveedores filtra en el cliente.
Lee en modo **solo-lectura**, parsea y agrega las transacciones (con dedup).

**Catálogo de remitentes** (`app/bank_senders.py`): **63 direcciones de 29 bancos/
fintech** (Banco de Chile, Edwards, Santander, BCI, Itaú, Scotiabank, BancoEstado,
Falabella/CMR, BICE, Consorcio, Ripley, Security, Coopeuch, Tenpo, Mach, Mercado
Pago, Global66, Fintual, Copec Pay, Prex, Los Héroes, Banco Internacional, etc.).
Consulta el catálogo en `GET /api/bank-senders`.

### Opción C — Etiqueta de Gmail "BANCOS" (la más simple, recomendada)
1. En Gmail crea **un filtro** con el texto que entrega `GET /api/bank-senders/gmail-filter`
   (un `from:(... OR ...)` con los 63 remitentes) y aplícale la etiqueta **BANCOS**.
   Marca "aplicar también a las conversaciones coincidentes" para etiquetar el histórico.
2. Llama `POST /api/ingest/email/imap` leyendo esa etiqueta:
```json
{ "account_id": 1, "host": "imap.gmail.com", "user": "tucorreo@gmail.com",
  "password": "APP_PASSWORD", "folder": "BANCOS", "use_bank_senders": false }
```
Gmail expone cada etiqueta como una "carpeta" IMAP, así que basta con leer `folder: "BANCOS"`.
El filtrado ya lo hizo Gmail; el app solo parsea y agrega (con dedup).

**Formatos probados en el parser**: Banco de Chile, Santander, BCI, Itaú,
BancoEstado, Mach, Mercado Pago, Falabella (patrón genérico + `received_date`).

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
