from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

from app.utils.text import normalize_text, normalize_title


def stable_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def title_hash(title: str) -> str:
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()


def is_similar_title(left: str, right: str, threshold: float = 0.88) -> bool:
    normalized_left = normalize_title(left)
    normalized_right = normalize_title(right)
    if not normalized_left or not normalized_right:
        return False
    return SequenceMatcher(None, normalized_left, normalized_right).ratio() >= threshold


def extract_simple_entities(title: str) -> set[str]:
    entities = set(re.findall(r"\b[A-Z][A-Za-z0-9.-]{2,}\b", title or ""))
    known = {
        "OpenAI",
        "Google",
        "DeepMind",
        "Anthropic",
        "Microsoft",
        "NVIDIA",
        "Meta",
        "Gemini",
        "Claude",
        "GPT",
        "Llama",
        "Mistral",
        "DeepSeek",
    }
    lowered = title.lower()
    entities.update(name for name in known if name.lower() in lowered)
    return entities
