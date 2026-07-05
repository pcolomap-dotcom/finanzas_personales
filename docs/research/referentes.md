# Investigación: Referentes Fintonic (ES) y Kuanto (CL)

> Producido por el agente **Analista-Referentes** · 2026-07-04

## Fintonic (España)
- **Modelo**: gratis para el usuario; monetiza intermediando préstamos/seguros
  (cobra a las entidades, no al usuario). Los datos de gasto alimentan ese negocio.
- **Features**: agregación de 150+ entidades; categorización automática por ML;
  +50 tipos de alertas (comisiones, descubiertos, cargos duplicados, vencimientos,
  nómina); presupuestos por categoría en tiempo real; detección de suscripciones y
  "gastos hormiga"; objetivos de ahorro; **FinScore** (score de salud financiera).
- **Conexión**: **PSD2 / Open Banking**. Fintonic fue la 1ª fintech con licencia del
  Banco de España como **AISP** (lectura de cuentas) + **PISP** (iniciación de pagos).
  Acceso **solo-lectura**; el usuario se autentica en su banco con **SCA** (auth
  reforzada). Apoyo en APIs PSD2 y, como *fallback* permitido, scraping bajo estándar
  PSD2. Agregadores del ecosistema: Afterbanks, Tink, GoCardless/Nordigen, Unnax.

## Kuanto (Chile)
- **Modelo**: de pago, ~$6.990 CLP/mes ($4.990 lanzamiento). Muy nueva (ago-2025).
- **Features**: registro automático de transacciones, categorización con IA que
  aprende de correcciones, consolidación multi-cuenta/tarjeta, canal Telegram/IA.
- **Conexión**: **reenvío de emails de notificación bancaria + parser IA**. NO usa
  credenciales ni open banking. Bancos con aviso por compra (Banco de Chile, Bci,
  Mach) → casi tiempo real; otros (Santander, Falabella) → cartolas mensuales.
- **Por qué así**: Chile **aún no tiene open banking operativo**. Ley Fintech
  N°21.521 (2023) creó el **Sistema de Finanzas Abiertas**; CMF **NCG N°514** (2024)
  lo regula; **Etapa 1 en vigor jul-2026**. Hasta entonces no hay APIs obligatorias.

## Ecosistema chileno relevante
- **Fintoc**: pagos A2A + agregación por **credenciales** del usuario (B2B). YC.
- **Belvo**: agregador open finance LatAm (B2B), modelo credencial→extracción.
- **Destácame**: scoring con datos alternativos (+2,2M usuarios).
- **Fintual** (inversión, regulada CMF), **Tenpo** (cuenta remunerada).

## Features imprescindibles para alternativa personal y gratuita
**Must-have**: ingesta automática sin guardar credenciales · categorización auto
editable con aprendizaje · vista consolidada multi-cuenta · presupuestos por
categoría · detección de recurrentes/suscripciones · re-categorización manual.
**Nice-to-have**: alertas configurables · objetivos de ahorro · score de salud
financiera simple · reportes/tendencias + export CSV · bot conversacional · multi-moneda.

## Recomendación de conexión
- **CL (2026)**: empezar con **email-parsing** (modelo Kuanto) o **import de cartolas**;
  migrar a APIs del SFA cuando la Etapa 1 (jul-2026) se despliegue; Fintoc/Belvo si
  se quiere agregación por credenciales (Fintoc gratis hasta 5 cuentas persona natural).
- **ES**: **PSD2/AISP** vía agregador con tier gratuito (GoCardless/Nordigen). Solo-lectura.
- Para uso personal: **priorizar métodos que NO almacenen credenciales bancarias**.
