# 💰 Finanzas App

App personal, **gratuita** y **local-first** para gestionar tus finanzas y
automatizar la lectura de tus cuentas bancarias **chilenas (CLP)** y **españolas (EUR)**.
Inspirada en **Fintonic** (España) y **Kuanto** (Chile), pensada para uso propio y
sin coste: tus datos viven en tu equipo (SQLite), sin nube y sin guardar
credenciales bancarias.

## Estado
MVP en construcción. Fase 1 = **import manual de cartolas CSV** + categorización
automática + presupuestos. Ver `docs/ARCHITECTURE.md` y el roadmap de conexión.

## Requisitos
- Python 3.11+

## Puesta en marcha
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed        # crea la BD y carga categorías/reglas por defecto
uvicorn app.main:app --reload
```
Luego abre http://127.0.0.1:8000 — la PWA se sirve desde el mismo backend.

## Importar movimientos
1. Descarga la cartola de tu banco en CSV.
2. En la app: **Importar** → elige la cuenta y el preset del banco (o mapea columnas).
3. Las transacciones se categorizan solas; corrige lo que falle y la app aprende.

## Salud financiera
Pestaña **Salud**: score 0–100 que combina tus gastos y deudas — carga financiera
(cuota/ingreso), tasa de ahorro y endeudamiento — con recomendaciones por métrica.

## Traspasos internos
Pestaña **Traspasos**: detecta por igualdad de monto los movimientos entre tus
propias cuentas y los **sugiere** para excluirlos del resumen (tras tu aprobación).
También sugiere pagos de tarjeta/línea/crédito y, al aplicarlos, **reduce la deuda**.

## Deudas (informe CMF)
Pestaña **Deudas**: sube el CSV del informe de deudas / Boletín Comercial (con tu RUT)
para ver tu **deuda total**, **cuota mensual** y el detalle de tus créditos (destaca
los de consumo). Compatible con el formato oficial CMF.

## Conexión automática (Fase 2)
- 🇨🇱 **Chile**: ingesta de emails de aviso bancario (modelo Kuanto), manual o por IMAP.
- 🇪🇸 **España**: open banking PSD2 solo-lectura vía GoCardless/Nordigen (free tier).
- Guía paso a paso: `docs/CONEXION.md`.

## Tests
```bash
cd backend && python tests/test_email_parser.py && python tests/test_psd2_mapper.py
```

## Documentación
- `docs/AGENTS.md` — flota de agentes del proyecto.
- `docs/CONEXION.md` — conexión automática de cuentas (CL emails + ES PSD2).
- `docs/LOG.md` — log de acciones de cada agente.
- `docs/ARCHITECTURE.md` — decisiones técnicas y modelo de datos.
- `docs/research/referentes.md` — investigación de Fintonic y Kuanto.
