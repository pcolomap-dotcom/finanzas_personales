# 🔎 Buscador IA de empleo según tu CV

Herramienta local (CLI) que busca ofertas, las evalúa con Claude contra tu CV genérico
y te deja **listo para postular** solo a las que de verdad encajan.

## Cómo funciona

```
fuentes ──► dedup ──► prefiltro (gratis) ──► evaluación IA 2 sentidos ──► informe ──► paquete de postulación
```

1. **Recopila tu información** (`profile.json`): CV (.pdf/.docx/.txt/.md), puestos objetivo,
   ubicaciones/remoto, salario mínimo, dealbreakers y respuestas base de screening.
2. **Busca ofertas** en fuentes gratuitas:
   - **Get on Board** (Chile/LatAm), **Remotive** (remoto), **Arbeitnow** (Europa) — APIs públicas.
   - **Archivos JSON/CSV** tuyos: pega ofertas de LinkedIn, InfoJobs, Indeed, Laborum, etc.
3. **Prefiltro sin LLM**: descarta por palabras excluidas, dealbreakers, ubicación y salario;
   ordena por keywords y solo envía al LLM las mejores `max_jobs_to_score` (controla el coste).
4. **Evaluación en dos sentidos** con Claude (salida JSON validada):
   - `candidate_fit` — ¿la oferta es lo que **tú** buscas?
   - `employer_fit` — ¿un **reclutador** te pasaría el filtro? Extrae must-haves y los contrasta
     con evidencia del CV, sin inventar experiencia.
   - Solo es **✅ Postular** si ambos superan el umbral y faltan ≤ N must-haves. El score final es la
     media geométrica, así que una oferta "bonita" donde no cumples requisitos no sube.
5. **Paquete de postulación** (`pack`): carta adaptada, ajustes al CV, respuestas de screening y
   brechas a preparar. **No se envía automáticamente**: el auto-envío falla a menudo en portales
   (Workday, Greenhouse, LinkedIn...) y suele violar sus términos. Tú haces clic en "postular".
6. **Seguimiento** en SQLite local: no reevalúa ofertas ya vistas (no pagas dos veces) y guarda
   el estado (`recommended`, `maybe`, `applied`, `discarded`...).

## Puesta en marcha

```bash
pip install -r job_search/requirements.txt
mkdir -p job_search/data && cp ~/mi_cv.pdf job_search/data/cv.pdf
cp job_search/profile.example.json job_search/profile.json   # edítalo
export ANTHROPIC_API_KEY=...          # sin clave → modo heurístico gratis

python -m job_search search           # busca, evalúa y escribe job_search/data/report.md
python -m job_search list             # recomendadas + a revisar
python -m job_search pack <uid>       # carta + respuestas → job_search/data/applications/<uid>.md
python -m job_search mark <uid> applied
```

Opciones: `search --no-llm` (solo heurística), `search --rescore` (reevalúa todo).

## Coste
El CV y las preferencias van en un prefijo con **prompt caching**, así que cada oferta adicional
solo paga la descripción de la oferta y la respuesta. Ajusta `llm.max_jobs_to_score` y
`llm.effort` (`low` | `medium` | `high`) en el perfil.

## Privacidad
`job_search/data/` (CV, BD, informes) y `job_search/profile.json` están en `.gitignore`.
El CV solo sale de tu equipo hacia la API de Anthropic cuando usas el modo IA.

## Tests
```bash
python job_search/tests/test_job_search.py
```
