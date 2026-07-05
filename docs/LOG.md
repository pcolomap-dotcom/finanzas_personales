# Log de acciones de la flota

Registro cronológico de lo que hace cada agente.

---

## 2026-07-04

### 🧭 Coordinador (agente principal)
- Aclarada la naturaleza del proyecto: **repositorio nuevo**, sin relación con la
  polla mundial ni el dashboard de moneda.
- Creado workspace nuevo en `/home/user/finanzas-app` con git inicializado.
- Definida la flota de agentes (`docs/AGENTS.md`).
- Lanzados en paralelo (background) los agentes de investigación:
  - 🔎 `Analista-Referentes`
  - 🏦 `Explorador-OpenBanking`

### 🔎 Analista-Referentes  ✅ COMPLETADO
Hallazgos clave (informe completo en `docs/research/referentes.md`):
- **Fintonic (ES)**: gratis al usuario (monetiza intermediando préstamos/seguros).
  Conexión vía **PSD2/Open Banking** con licencia propia (AISP+PISP), solo-lectura,
  autenticación reforzada en el banco. Features: agregación 150+ entidades,
  categorización ML, +50 alertas, presupuestos, detección de suscripciones,
  objetivos de ahorro, **FinScore** (salud financiera).
- **Kuanto (CL)**: de pago (~$6.990 CLP/mes). Chile **no tiene open banking operativo**
  (Ley Fintech 21.521; SFA/CMF NCG 514; Etapa 1 recién entra en vigor **jul-2026**).
  Por eso Kuanto usa **reenvío de emails de notificación + parser IA** — sin credenciales.
- **Features must-have** para alternativa gratuita: ingesta sin guardar credenciales,
  categorización auto editable, vista consolidada multi-cuenta, presupuestos,
  detección de recurrentes, re-categorización manual.

### 🏦 Explorador-OpenBanking  ⚠️ INTERRUMPIDO (límite de sesión de la cuenta, reset 19:30 UTC)
- Alcanzó un hallazgo: **Fintoc es gratis hasta 5 cuentas de persona natural (CL)**.
- Investigación pendiente de completar (GoCardless/Nordigen free tier ES, Belvo, etc.).
- **Mitigación**: no se re-lanza para no consumir presupuesto; el Coordinador retoma
  la parte crítica inline. Como el MVP parte con **import manual CSV/PDF**, esta
  investigación no bloquea la construcción.

### 🏗️ Arquitecto (asumido inline por el Coordinador)  ✅ COMPLETADO
- Decisiones del usuario: **PWA self-host · SQLite local-first · import CSV/PDF primero**.
- Redactado `docs/ARCHITECTURE.md`: stack (FastAPI + SQLAlchemy + SQLite + PWA vanilla),
  6 ADRs, modelo de datos (7 tablas), motor de categorización híbrido, roadmap de conexión.

### 🛠️ Constructor (asumido inline por el Coordinador)  ✅ COMPLETADO
- Backend: `db.py`, `models.py` (Account, Category, Transaction, Rule, MerchantMemory,
  Budget, ImportBatch), `categorize.py`, `importers.py` (CSV con parseo de montos
  CL/ES y dedup), `seed.py`, `main.py` (API REST + sirve la PWA).
- Frontend PWA sin dependencias externas: `index.html`, `styles.css`, `app.js`,
  `manifest.webmanifest`, `sw.js`, `icon.svg` (funciona offline).
- Datos de ejemplo: `samples/banco_de_chile.csv` y `samples/bbva_espana.csv`.

### 🔒 Verificación (Coordinador)  ✅ COMPLETADO
- `pip install` + `python -m app.seed` → 23 categorías, 142 reglas, 2 cuentas demo.
- Arrancado uvicorn; probado `/api/health`, `/api/accounts`.
- Importadas ambas cartolas: 10 CL + 10 ES, categorización automática correcta
  (Lider→Supermercado, Netflix→Suscripciones, Iberdrola→Servicios básicos, etc.).
- Parseo de montos verificado: CL `1.850.000`→1850000, ES `-64.35`→-64.35.
- Dedup verificado: reimportar omite las 10 duplicadas.
- Recategorización verificada: cambiar Doggis a "Compras" y el motor lo **aprende**.
- Captura real de la PWA con Chromium. **Bug visual detectado y corregido**: los
  rellenos de las barras (`<span>` inline) ignoraban `height/width` → añadido
  `display:block`. Re-capturado: barras con color OK en claro y oscuro.

### 🧭 Coordinador — Publicación
- Usuario eligió **repo nuevo privado** (1-A) y **automatizar conexión** (2-1).
- El integration de GitHub de la sesión **no puede crear repos** (403, scope acotado
  a `polla-mundial-2026`). Mitigación: entregado tarball con historial git al usuario
  + comandos para subirlo a su repo nuevo.

---

## Fase 2 — Automatización de conexión bancaria

### 🇨🇱 CL — Parser de emails (modelo Kuanto)  ✅ COMPLETADO
- `email_ingest.py`: parser robusto (monto CLP/EUR, comercio, fecha num/es,
  detección ingreso vs gasto). `imap_sync.py`: lectura IMAP solo-lectura (stdlib).
- Endpoints `POST /api/ingest/email/text` y `/api/ingest/email/imap`.
- Refactor: `insert_transaction()` compartido entre CSV y email (categoriza + dedup).
- **Tests 6/6 verde** (Banco de Chile, Santander, BCI, Mach, abono, BBVA EUR).
- Verificado en vivo: STARBUCKS insertado + dedup en reintento.

### 🇪🇸 ES — Cliente PSD2 GoCardless  ✅ COMPLETADO (scaffold + mapper testeado)
- `psd2_gocardless.py`: cliente (token, institutions, requisition, transactions).
- `psd2_mapper.py`: GoCardless JSON → transacciones. **Test verde**.
- Endpoints `POST /api/psd2/institutions|requisition|import`.
- La conexión en vivo requiere claves gratuitas del usuario (documentado).
- Guía completa en `docs/CONEXION.md`.

### 🔒 Verificación Fase 2
- `import app.main` OK (21 rutas). Ambas suites de tests en verde.
