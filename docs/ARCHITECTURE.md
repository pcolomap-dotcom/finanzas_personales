# Arquitectura — Finanzas App (MVP)

App personal, gratuita y **local-first** para consolidar y categorizar finanzas de
cuentas **chilenas (CLP)** y **españolas (EUR)**. Inspirada en Fintonic y Kuanto.

## Decisiones (ADRs resumidos)

| # | Decisión | Motivo |
|---|----------|--------|
| ADR-1 | **PWA self-host** servida por el backend | Un solo proceso, instalable en móvil/PC, gratis |
| ADR-2 | **SQLite local-first** | Privacidad de datos bancarios, cero coste, sin nube |
| ADR-3 | **Backend Python + FastAPI** | Rápido, tipado, sirve API + estáticos; afín al usuario |
| ADR-4 | **Ingesta = import CSV/PDF primero** | Funciona hoy, sin credenciales; base para automatizar |
| ADR-5 | **Sin credenciales bancarias almacenadas** | Seguridad; alinea con modelo Kuanto/PSD2 |
| ADR-6 | **Multi-moneda por transacción** (CLP/EUR) | Cuentas en 2 países; totales por moneda, FX opcional |

## Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.0, SQLite.
- **Frontend**: PWA estática (HTML + JS vanilla + Chart.js), servida por FastAPI.
- **Sin build step**: se ejecuta con `uvicorn` y se abre en el navegador.

## Modelo de datos
- **Account**: id, name, bank, country(CL|ES), currency(CLP|EUR), type, created_at.
- **Category**: id, name, parent_id, kind(expense|income|transfer), color, icon.
- **Transaction**: id, account_id, date, description, raw_description, amount(+ingreso/−gasto),
  currency, category_id, is_recurring, source(csv|pdf|email|api), dedup_hash, created_at.
- **Rule**: id, pattern, match_type(contains|regex), category_id, priority.
- **MerchantMemory**: normalized_merchant → category_id (aprende de correcciones).
- **Budget**: id, category_id, amount, currency, period(monthly).
- **ImportBatch**: id, account_id, filename, imported_at, count (auditoría/dedup).

## Categorización (motor híbrido)
1. **MerchantMemory** (lo que el usuario ya corrigió) — máxima prioridad.
2. **Rules** por keyword/regex sobre la glosa (seed con comercios CL y ES).
3. Sin match → categoría "Sin categorizar"; el usuario recategoriza y se aprende.

## Import CSV
- Presets de mapeo por banco (columnas fecha/glosa/monto/cargo/abono).
- Parseo de montos con formato **CL (1.234)** y **ES (1.234,56)**.
- Dedup por `dedup_hash = sha1(account, date, amount, raw_description)`.

## API (resumen)
- `POST/GET /api/accounts`
- `POST /api/import/csv` (multipart)
- `GET /api/transactions`, `PATCH /api/transactions/{id}` (recategoriza + aprende)
- `GET /api/summary?month=YYYY-MM` (ingreso/gasto por categoría y moneda)
- `GET/POST /api/categories`, `/api/rules`, `/api/budgets`, `GET /api/budgets/status`

## Roadmap de conexión bancaria (post-MVP)
1. **Fase 1 (MVP)**: import CSV/PDF manual. ✅ objetivo actual.
2. **Fase 2 CL**: parser de emails de notificación (modelo Kuanto) vía IMAP/Gmail.
3. **Fase 2 ES**: agregación PSD2 solo-lectura con **GoCardless/Nordigen** (free tier).
4. **Fase 3 CL**: **Fintoc** (gratis ≤5 cuentas persona natural) o APIs del **SFA** (jul-2026+).

## Seguridad y privacidad
- Datos en SQLite local; sin nube por defecto.
- No se guardan credenciales bancarias.
- `.gitignore` excluye la base de datos y archivos importados.
