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

---

## Fase 3 — Soporte cartola real Banco de Chile (.xls)

- Usuario probó la app local en Windows y subió su **cartola real** `.xls` de junio.
- Detectado: es **Excel binario OLE2**, con encabezados en fila 25
  (`Fecha | Descripción | Canal | Cargos | Abonos | Saldo`) y **fechas `dd/mm` sin año**.
- `importers.py`: añadido lector Excel (`xlrd` para .xls, `openpyxl` para .xlsx),
  detección de fila de encabezados, **inferencia de año** desde la fecha de emisión,
  y dispatcher `import_file()` (CSV vs Excel por extensión/magia). Procesador de filas
  compartido entre CSV y Excel.
- **Probado con la cartola real: 27 movimientos importados, 9 omitidos** (saldo
  inicial/filas vacías), año 2026 inferido, cargos/abonos correctos.
- Categorización mejorada: nueva categoría **Seguros** + reglas CL (Google Play,
  línea de crédito, seguros, devoluciones). `seed.py` ahora **idempotente**
  (re-ejecutar añade solo lo nuevo: +1 categoría, +17 reglas).
- Nuevo endpoint `POST /api/maintenance/recategorize` + **botón en la UI** para
  aplicar reglas a movimientos "Sin categorizar" (6/7 pendientes resueltos).
- Fix de arranque en Windows: usar `python -m uvicorn` (uvicorn no queda en PATH).

---

## Fase 4 — Módulo de Deudas (informe CMF / Boletín Comercial)

- Usuario subió su **informe de deudas real** (CMF) y pidió considerar sus dos
  créditos de consumo en las finanzas.
- Nuevo modelo `Debt` + importador `debts.py` (parsea el CSV oficial CMF: institución,
  tipo de crédito, saldo actual, carga financiera/cuota, fechas, mora; dedup por
  código de operación, actualiza saldos al reimportar).
- API: `GET /api/debts` (items + totales: deuda total, cuota mensual, consumo, mora)
  y `POST /api/debts/import`.
- Frontend: nueva pestaña **Deudas** con KPIs, importador y listado (destaca consumo).
- **Probado con el informe real**: 8 operaciones · **deuda total $18.212.327** ·
  **cuota mensual $424.931** · **consumo $17.875.953** (BCI + Santander).
- App con 24 rutas; suites de tests en verde.
- Nota: no se pudo generar screenshot (el sandbox mató los procesos que abren puerto);
  verificado por datos e importación directa.

---

## Fase 5 — Cartola Santander España + planificación de cuotas

- **Cartola Santander España (.xls)**: encaja con el importador Excel existente
  (encabezados fila 7: `FECHA OPERACIÓN | CONCEPTO | IMPORTE EUR`). Probada:
  **46 movimientos importados** en la cuenta EUR, importes/fechas correctos.
- Reglas ES añadidas al seed (Five Guys, Primark, El Corte Inglés, Ouigo, museos…).
- **Planificación de cuotas de deuda** (a partir de datos del usuario):
  - `Debt` ahora tiene `payment_day` y `last_paid_period`; mini-migración SQLite
    (`ALTER TABLE ADD COLUMN`) para no perder datos existentes.
  - Endpoints `PATCH /api/debts/{id}` (cuota, día, saldo) y
    `POST /api/debts/{id}/mark_paid` (marca la cuota del mes como pagada).
  - `GET /api/debts` calcula **próximo vencimiento** por deuda y **"por pagar este mes"**.
  - Reimportar el informe CMF ya **no pisa** una cuota editada con un 0.
  - UI Deudas: cuota y día editables, próximo vencimiento, botón "marcar cuota pagada".
- **Verificado con datos reales**: BCI cuota $345.042 día 17 → vence 17-jul;
  Santander $133.932 día 5, marcada pagada → próximo 5-ago; por pagar este mes $345.042.
- App con 26 rutas; suites de tests en verde.

---

## Fase 6 — Catálogo de remitentes bancarios (modelo Kuanto)

- Usuario aportó la **lista de remitentes** que reenvía Kuanto (bancos/fintech CL).
- Nuevo `bank_senders.py`: **63 direcciones → 29 bancos**, con `bank_for_sender()`
  (exacto o por dominio), `is_bank_sender()` y `gmail_from_query()` (búsqueda nativa
  Gmail `from:(...) newer_than:Nd`).
- `imap_sync.fetch_bank_emails(use_bank_senders=True)`: filtra automáticamente a los
  bancos conocidos (X-GM-RAW en Gmail; filtrado en cliente en otros proveedores) y
  etiqueta cada correo con su banco.
- `POST /api/ingest/email/imap` gana `use_bank_senders` (default True) y reporta
  `por_banco`. Nuevo `GET /api/bank-senders` expone el catálogo.
- Tests: parser ampliado (Itaú, Mercado Pago, BancoEstado) 9/9; nuevo
  `test_bank_senders.py` 10/10 (63 remitentes).
- App con 27 rutas. Doc actualizada en `docs/CONEXION.md`.

---

## Fase 7 — Lectura por etiqueta de Gmail "BANCOS"

- Usuario prefiere crear un filtro Gmail que etiquete los correos bancarios como
  **BANCOS** y que el app lea solo esa etiqueta.
- `ImapSyncIn` gana `folder` (default "INBOX"); se lee `folder: "BANCOS"` (Gmail
  expone cada etiqueta como carpeta IMAP). Con la etiqueta como filtro se usa
  `use_bank_senders: false`.
- Nuevo `GET /api/bank-senders/gmail-filter`: entrega el texto `from:(...)` listo
  para crear el filtro + pasos. App con 28 rutas.
- Doc `docs/CONEXION.md`: nueva "Opción C — Etiqueta de Gmail (recomendada)".

---

## Fase 8 — Pantalla "Correo" en la interfaz

- Nueva pestaña **Correo** en la PWA (sin usar endpoints a mano):
  - Formulario de conexión: cuenta destino, IMAP host, correo, contraseña de
    aplicación, etiqueta/carpeta (default BANCOS), días; botón **Sincronizar ahora**
    (`/ingest/email/imap`). Si la carpeta es INBOX activa `use_bank_senders`; si es
    una etiqueta, confía en el filtro de Gmail.
  - Botón **Mostrar texto del filtro** (`/bank-senders/gmail-filter`) con textarea
    de solo lectura + botón **Copiar** (clipboard) y los pasos.
  - Caja **Probar con un correo pegado** (`/ingest/email/text`) que muestra lo
    detectado (glosa, monto, fecha).
- CSS para inputs de texto/email/password y textarea.
- Validado: `node --check app.js` OK; todos los IDs referenciados existen en el HTML.
  (No se pudo screenshot por la restricción del sandbox con puertos.)

---

## Fase 9 — Parser de comprobantes reales (Google Takeout del usuario)

- Usuario aportó export real (mbox, etiqueta BANCOS): **161 correos, ene–jul 2026**.
- El parser genérico anterior sacaba glosas basura (HTML) y montos erróneos.
- **Reescrito `email_ingest.parse_email`** para comprobantes reales:
  - `html.unescape` + montos por etiqueta ("Monto transferido", "Monto del pago",
    "Recibiste X CLP", …) reuniendo candidatos y **prefiriendo CLP** (p. ej. pago
    de tarjeta en USD → toma el "Monto $55.199", no el "USD$61,11").
  - Soporte de importes en **€** y USD; signo por tipo de comprobante; fecha
    numérica o en texto ("27 de abril de 2026") con guardia de año (≥2015).
  - **Glosa desde el asunto** (limpio y descriptivo) y extracción de comercio solo
    en avisos de compra (con lista de descarte anti-ruido).
  - Descarta cartolas, estados de cuenta, claves, bloqueos, avisos de seguridad.
- Resultado sobre el mbox real: descripciones legibles ("Transferencia a Terceros",
  "Pago de Tarjeta de Crédito", "Recibiste dinero…") y montos correctos.
- Detectadas **varias cuentas**: Banco de Chile, Global66 (EUR/CLP), Santander, Mach,
  Mercado Pago, BCI, Scotiabank. (Import pendiente de decisión del usuario por
  solapamiento con la cartola y traspasos internos.)
- Tests: parser 9/9 (incl. EUR), bank_senders 10/10, psd2 OK. App 28 rutas.

---

## Fase 10 — Traspasos internos + deudas por tipo + pago que limpia deuda

- **Traspasos internos** (a pedido del usuario: intuir por igualdad de monto y
  sugerir esperando aprobación):
  - `transfers.py`: detecta pares salida↔entrada del **mismo monto** en cuentas
    distintas (±4 días) y cargos que parecen **pago de tarjeta/línea/crédito**.
  - `Transaction`: nuevas columnas `is_internal`, `transfer_checked`, `debt_id`
    (con micro-migración SQLite).
  - Endpoints `GET /api/transfers/suggestions`, `POST confirm_pair`,
    `confirm_debt`, `dismiss`. El resumen **excluye** los internos de gasto/ingreso.
  - UI: pestaña **Traspasos** con sugerencias y botones Aprobar/Ignorar.
- **Deudas por tipo independiente**: subtotales/KPIs de **Consumo / Tarjetas /
  Líneas de crédito** por separado.
- **El pago limpia la deuda**: al aplicar un pago sugerido a una deuda, baja su saldo
  (probado: 100.000 − 30.000 → 70.000) y el cargo se marca como interno.
- Verificado con datos reales/controlados; tests 3/3 en verde; app con 32 rutas.

---

## Fase 11 — Indicador de Salud Financiera

- `GET /api/salud?month&income`: combina gastos + deudas (base CLP) y calcula un
  **score 0–100** con tres métricas ponderadas:
  - **Carga financiera** = cuota mensual de deudas / ingreso (ideal < 35%).
  - **Tasa de ahorro** = (ingreso − gasto − cuota) / ingreso (ideal > 20%).
  - **Endeudamiento** = deuda total / ingreso mensual (meses; ideal < 6).
  - Bandas: Excelente / Buena / Regular / Delicada.
- El ingreso se toma de los movimientos del mes o se puede **fijar manualmente**
  (se guarda en el navegador).
- UI: pestaña **Salud** con medidor circular (conic-gradient), resumen
  (ingreso/gasto/cuotas/balance/deuda) y las métricas con estado (verde/ámbar/rojo).
- Verificado: score 73 "Buena" con datos reales; app con 33 rutas; `node --check` OK.
