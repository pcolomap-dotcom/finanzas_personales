"""Paquete de postulación: carta adaptada + respuestas a preguntas de screening.

No enviamos la solicitud automáticamente: los formularios (LinkedIn, Workday, Greenhouse,
portales propios) cambian constantemente, el auto-envío falla con frecuencia y suele violar
sus términos de uso. En su lugar se prepara todo para que postular te lleve 2 minutos.
"""
from __future__ import annotations

from pathlib import Path

from .profile import Profile
from .sources import Job
from .store import DATA_DIR

PACK_PROMPT = """Prepara el material para postular a la oferta usando SOLO hechos del CV.
Devuelve Markdown con estas secciones:

## Carta de presentación
Máximo 220 palabras, en el idioma de la oferta, sin clichés ni frases infladas. Conecta 2-3 logros
concretos del CV con los requisitos principales de la oferta.

## Ajustes sugeridos al CV
3-6 viñetas: qué destacar, reordenar o reformular (sin inventar experiencia) para esta oferta.

## Respuestas a preguntas de screening
Respuestas breves a preguntas típicas probables para esta oferta, usando las respuestas base del
candidato cuando apliquen. Marca con [COMPLETAR] lo que no se pueda responder con la información dada.

## Requisitos a preparar para la entrevista
Brechas detectadas y cómo abordarlas honestamente."""


def build_pack(job: Job, match: dict | None, profile: Profile, cv_text: str, client=None) -> Path:
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    from .matcher import _job_block

    context = (
        f"<cv>\n{cv_text}\n</cv>\n\n<respuestas_base>\n{profile.screening_answers}\n</respuestas_base>\n\n"
        f"{_job_block(job)}\n\n<evaluacion_previa>\n{match}\n</evaluacion_previa>"
    )
    with client.beta.messages.stream(
        model=profile.llm.model,
        max_tokens=64000,
        messages=[{"role": "user", "content": f"{context}\n\n{PACK_PROMPT}"}],
        output_config={"effort": profile.llm.effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó generar el paquete")
    body = "".join(b.text for b in response.content if b.type == "text")

    out_dir = DATA_DIR / "applications"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{job.uid}.md"
    header = f"# {job.title} — {job.company}\n\n- Enlace para postular: {job.url}\n- Fuente: {job.source}\n\n"
    path.write_text(header + body, encoding="utf-8")
    return path
