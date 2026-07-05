"""Motor de categorización híbrido: memoria de comercio + reglas."""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy.orm import Session

from .models import MerchantMemory, Rule


def normalize(text: str | None) -> str:
    """Minúsculas, sin acentos ni símbolos, espacios colapsados."""
    text = text or ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def merchant_key(text: str | None) -> str:
    """Clave estable de comercio: primeras palabras significativas de la glosa."""
    norm = normalize(text)
    words = [w for w in norm.split() if len(w) > 2 and not w.isdigit()]
    return " ".join(words[:3]) if words else norm


def categorize(db: Session, description: str) -> int | None:
    """Devuelve category_id según memoria de comercio y luego reglas."""
    norm = normalize(description)
    key = merchant_key(description)

    if key:
        mem = (
            db.query(MerchantMemory)
            .filter(MerchantMemory.normalized_merchant == key)
            .first()
        )
        if mem:
            return mem.category_id

    for rule in db.query(Rule).order_by(Rule.priority.asc()).all():
        if rule.match_type == "regex":
            try:
                if re.search(rule.pattern, norm):
                    return rule.category_id
            except re.error:
                continue
        elif normalize(rule.pattern) and normalize(rule.pattern) in norm:
            return rule.category_id
    return None


def remember(db: Session, description: str, category_id: int) -> None:
    """Registra la corrección del usuario para futuras transacciones del comercio."""
    key = merchant_key(description)
    if not key:
        return
    mem = (
        db.query(MerchantMemory)
        .filter(MerchantMemory.normalized_merchant == key)
        .first()
    )
    if mem:
        mem.category_id = category_id
    else:
        db.add(MerchantMemory(normalized_merchant=key, category_id=category_id))
