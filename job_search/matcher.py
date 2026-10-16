"""Evaluación de encaje en DOS sentidos con Claude.

1. candidate_fit: ¿la oferta encaja con lo que YO busco? (rol, ubicación, salario, seniority)
2. employer_fit: ¿un reclutador me pasaría el filtro? (requisitos obligatorios cumplidos)

Solo se recomienda postular si ambos superan el umbral: enviar cientos de solicitudes
a ofertas donde no cumples requisitos es perder el tiempo (el tuyo y el del empleador).
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .profile import Profile
from .sources import Job

MAX_DESC_CHARS = 12000


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_fit: int
    employer_fit: int
    must_haves_met: list[str]
    must_haves_missing: list[str]
    nice_to_haves_met: list[str]
    red_flags: list[str]
    summary: str
    verdict: Literal["apply", "maybe", "skip"]


SYSTEM_PROMPT = """Eres un reclutador técnico senior y, a la vez, un asesor de carrera honesto.
Evalúas una oferta de empleo contra el CV y las preferencias de un candidato, desde DOS perspectivas:

- candidate_fit (0-100): cuánto encaja la oferta con lo que el candidato busca (rol objetivo,
  ubicación/remoto, salario mínimo, seniority, idiomas, dealbreakers).
- employer_fit (0-100): probabilidad realista de que el candidato pase el primer filtro del empleador.
  Extrae de la oferta los requisitos OBLIGATORIOS (must-haves) y los deseables (nice-to-haves) y
  compáralos con evidencia concreta del CV. No inventes experiencia que el CV no muestre; experiencia
  transferible cuenta solo si es claramente equivalente.

Reglas del veredicto:
- "apply": ambos puntajes altos y como mucho un must-have dudoso.
- "maybe": encaje parcial que merece una revisión humana.
- "skip": faltan requisitos clave, choca con un dealbreaker o no es lo que busca el candidato.

Responde en español. `summary`: 2-3 frases concretas que citen requisitos y evidencia del CV.
`red_flags`: señales de alerta de la oferta (salario oculto con exigencias altas, descripción vaga,
'rockstar', comisiones, etc.) o desajustes graves; lista vacía si no hay."""


def _client():
    import anthropic

    return anthropic.Anthropic()


def _job_block(job: Job) -> str:
    salary = ""
    if job.salary_min or job.salary_max:
        salary = f"{job.salary_min or '?'}-{job.salary_max or '?'} {job.salary_currency}"
    return (
        f"<oferta>\nTítulo: {job.title}\nEmpresa: {job.company}\nUbicación: {job.location}"
        f"\nRemoto: {'sí' if job.remote else 'no/desconocido'}\nSalario: {salary or 'no indicado'}"
        f"\nURL: {job.url}\n\nDescripción:\n{job.description[:MAX_DESC_CHARS]}\n</oferta>"
    )


def evaluate(job: Job, profile: Profile, cv_text: str, client=None) -> MatchResult:
    client = client or _client()
    # CV + preferencias son idénticos para todas las ofertas → prefijo cacheado.
    system = [
        {"type": "text", "text": SYSTEM_PROMPT},
        {
            "type": "text",
            "text": f"<cv>\n{cv_text}\n</cv>\n\n<preferencias>\n{profile.preferences_text()}\n</preferencias>",
            "cache_control": {"type": "ephemeral"},
        },
    ]
    schema = MatchResult.model_json_schema()
    response = client.beta.messages.create(
        model=profile.llm.model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": _job_block(job)}],
        output_config={"effort": profile.llm.effort, "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó evaluar esta oferta")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Respuesta truncada (max_tokens)")
    text = next(b.text for b in response.content if b.type == "text")
    result = MatchResult.model_validate(json.loads(text))
    result.candidate_fit = max(0, min(100, result.candidate_fit))
    result.employer_fit = max(0, min(100, result.employer_fit))
    return result


def heuristic(job: Job, profile: Profile, kw_score: float) -> MatchResult:
    """Modo gratis sin API key: solo puntaje por keywords, siempre requiere revisión humana."""
    return MatchResult(
        candidate_fit=int(kw_score), employer_fit=int(kw_score),
        must_haves_met=[], must_haves_missing=[], nice_to_haves_met=[], red_flags=[],
        summary="Puntaje heurístico por palabras clave (sin LLM). Revisa la oferta manualmente.",
        verdict="maybe" if kw_score >= 50 else "skip",
    )


def should_apply(result: MatchResult, profile: Profile) -> bool:
    t = profile.thresholds
    return (
        result.verdict == "apply"
        and result.candidate_fit >= t.candidate_fit
        and result.employer_fit >= t.employer_fit
        and len(result.must_haves_missing) <= t.max_missing_must_haves
    )


def combined_score(result: MatchResult) -> float:
    """Media geométrica: una oferta solo puntúa alto si encaja para AMBAS partes."""
    return round((result.candidate_fit * result.employer_fit) ** 0.5, 1)
