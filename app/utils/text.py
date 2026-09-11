from __future__ import annotations

import html
import re
from bs4 import BeautifulSoup


WHITESPACE_RE = re.compile(r"\s+")
URL_RE = re.compile(r"https?://\S+")


def strip_html(value: str) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return normalize_text(soup.get_text(" "))


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = value.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", value).strip()


def normalize_title(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^\w\sа-яё-]", " ", value, flags=re.IGNORECASE)
    return WHITESPACE_RE.sub(" ", value).strip()


def remove_telegram_noise(value: str) -> str:
    lines = []
    for line in (value or "").splitlines():
        clean = line.strip()
        lower = clean.lower()
        if not clean:
            continue
        if "подпис" in lower or "subscribe" in lower or "промокод" in lower:
            continue
        if lower.startswith(("реклама", "ad:", "sponsored")):
            continue
        lines.append(clean)
    return normalize_text("\n".join(lines))


def summarize_sentences(value: str, *, max_chars: int = 900, max_sentences: int = 5) -> str:
    text = normalize_text(value)
    if len(text) <= max_chars:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    picked: list[str] = []
    total = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if total + len(sentence) > max_chars and picked:
            break
        picked.append(sentence)
        total += len(sentence)
        if len(picked) >= max_sentences:
            break
    result = " ".join(picked).strip()
    return result or text[:max_chars].rstrip() + "..."


def compact_for_post(value: str, *, max_chars: int = 1200) -> str:
    text = summarize_sentences(value, max_chars=max_chars, max_sentences=6)
    text = URL_RE.sub("", text)
    return normalize_text(text)

