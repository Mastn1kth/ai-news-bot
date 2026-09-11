from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Source:
    name: str
    type: str
    url: str
    category: str
    tier: int
    trust_score: int
    language: str
    rewrite_policy: str
    enabled: bool
    disabled_reason: str = ""


@dataclass
class NewsItem:
    source_name: str
    source_type: str
    source_url: str
    original_url: str
    title: str
    raw_text: str
    cleaned_text: str
    generated_post: str
    language: str
    category: str
    score: int
    status: str
    reject_reason: str
    content_hash: str
    title_hash: str
    published_at_source: str | None
    found_at: str
    published_at_telegram: str | None = None
    telegram_message_id: str | None = None
    error_message: str | None = None


@dataclass
class FetchedItem:
    title: str
    url: str
    raw_text: str
    published_at: datetime | None
    language: str
    extra: dict[str, str] | None = None

