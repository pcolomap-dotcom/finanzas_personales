# Flota de Agentes — Finanzas App

App personal y gratuita para gestionar finanzas con automatización de cuentas
bancarias **chilenas** y **españolas**. Inspirada en Fintonic (ES) y Kuanto (CL).

## Agentes

| # | Agente | Rol | Entregable |
|---|--------|-----|-----------|
| 1 | 🔎 **Analista-Referentes** | Estudiar cómo funcionan Fintonic y Kuanto; extraer features imprescindibles | Informe de features priorizadas |
| 2 | 🏦 **Explorador-OpenBanking** | Buscar métodos **gratuitos** de conexión bancaria ES + CL | Comparativa + arquitectura de conexión |
| 3 | 🏗️ **Arquitecto** | Definir stack, modelo de datos, arquitectura | Diseño técnico + ADRs |
| 4 | 🛠️ **Constructor** | Scaffolding e implementación del MVP | Código base ejecutable |
| 5 | 🔒 **Revisor** (opcional) | Seguridad y privacidad de credenciales/datos financieros | Checklist de seguridad |

## Principios de diseño

- **Gratis de operar**: sin costes recurrentes obligatorios; free tiers y self-host.
- **Local-first / privacidad**: datos financieros del usuario bajo su control.
- **Conexión híbrida**: cada país usa el mejor método gratuito disponible.
- **Incremental**: MVP con import manual funcionando antes que automatización total.
