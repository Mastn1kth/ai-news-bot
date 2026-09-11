from __future__ import annotations

from datetime import datetime, timezone
from time import struct_time

import feedparser

from app.config import Settings
from app.fetchers.website_fetcher import fetch_article_text
from app.models import FetchedItem, Source
from app.utils.http import fetch_url
from app.utils.text import normalize_text, strip_html


def _parsed_time_to_datetime(value: struct_time | None) -> datetime | None:
    if value is None:
        return None
    return datetime(*value[:6], tzinfo=timezone.utc)


def _entry_text(entry: feedparser.FeedParserDict) -> str:
    parts: list[str] = []
    if entry.get("summary"):
        parts.append(strip_html(str(entry.summary)))
    for content in entry.get("content", []) or []:
        if content.get("value"):
            parts.append(strip_html(str(content.value)))
    return normalize_text(" ".join(parts))


def fetch_rss_source(source: Source, settings: Settings) -> tuple[list[FetchedItem], str, str]:
    result = fetch_url(source.url, timeout=settings.request_timeout, retries=settings.fetch_retries)
    if not result.ok:
        return [], result.error_code, result.error_message

    parsed = feedparser.parse(result.text)
    if parsed.bozo and not parsed.entries:
        return [], "parse_error", str(parsed.bozo_exception)
    if not parsed.entries:
        return [], "parse_error", "RSS contains no entries"

    fetched: list[FetchedItem] = []
    for entry in parsed.entries[: settings.max_items_per_source]:
        title = normalize_text(str(entry.get("title", ""))) or "Без заголовка"
        url = str(entry.get("link", "")).strip() or source.url
        raw_text = _entry_text(entry)
        if len(raw_text) < 350 and url:
            article_text, error_code, _ = fetch_article_text(url, settings, timeout=10, retries=1)
            if article_text and len(article_text) > len(raw_text):
                raw_text = normalize_text(f"{raw_text} {article_text}")
            elif error_code and not raw_text:
                raw_text = title
        published_at = _parsed_time_to_datetime(entry.get("published_parsed") or entry.get("updated_parsed"))
        fetched.append(
            FetchedItem(
                title=title,
                url=url,
                raw_text=raw_text or title,
                published_at=published_at,
                language=source.language,
                extra={"feed_url": source.url},
            )
        )
    return fetched, "", ""

