"""Perfil del candidato: preferencias + texto del CV."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent


class LLMConfig(BaseModel):
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    max_jobs_to_score: int = 25


class Thresholds(BaseModel):
    candidate_fit: int = 65   # ¿me interesa a mí?
    employer_fit: int = 70    # ¿cumplo lo que piden?
    max_missing_must_haves: int = 1


class Sources(BaseModel):
    getonbrd: bool = True
    remotive: bool = True
    arbeitnow: bool = False
    files: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    cv_path: str
    target_titles: list[str]
    keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_ok: bool = True
    min_salary: float = 0
    salary_currency: str = "EUR"
    languages: list[str] = Field(default_factory=list)
    seniority: str = ""
    dealbreakers: list[str] = Field(default_factory=list)
    screening_answers: dict[str, str] = Field(default_factory=dict)
    sources: Sources = Field(default_factory=Sources)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    thresholds: Thresholds = Field(default_factory=Thresholds)

    def preferences_text(self) -> str:
        """Resumen estable de preferencias (va en el prompt cacheado)."""
        p = self.model_dump(exclude={"cv_path", "sources", "llm", "thresholds", "screening_answers"})
        return json.dumps(p, ensure_ascii=False, indent=2)


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_profile(path: str | Path) -> Profile:
    return Profile.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_cv_text(path: str | Path) -> str:
    """Lee el CV en .txt/.md/.pdf/.docx y devuelve texto plano."""
    p = resolve(str(path))
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(p).pages)
    elif suffix == ".docx":
        from docx import Document  # python-docx (opcional)
        text = "\n".join(par.text for par in Document(p).paragraphs)
    else:
        text = p.read_text(encoding="utf-8")
    text = text.strip()
    if not text:
        raise ValueError(f"No se pudo extraer texto del CV: {p}")
    return text
