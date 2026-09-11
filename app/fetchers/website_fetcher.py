from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.config import Settings
from app.models import FetchedItem, Source
from app.utils.http import fetch_url
from app.utils.text import normalize_text, strip_html


def extract_article_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = normalize_text(soup.title.get_text(" ")) if soup.title else ""
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    candidates = soup.find_all(["article", "main"])
    if candidates:
        text = " ".join(candidate.get_text(" ") for candidate in candidates)
    else:
        text = soup.get_text(" ")
    return title, strip_html(text)


def fetch_article_text(url: str, settings: Settings, *, timeout: int | None = None, retries: int | None = None) -> tuple[str, str, str]:
    result = fetch_url(url, timeout=timeout or settings.request_timeout, retries=retries or settings.fetch_retries)
    if not result.ok:
        return "", result.error_code, result.error_message
    _, text = extract_article_text(result.text)
    return text, "", ""


def fetch_website_source(source: Source, settings: Settings) -> tuple[list[FetchedItem], str, str]:
    result = fetch_url(source.url, timeout=settings.request_timeout, retries=settings.fetch_retries)
    if not result.ok:
        return [], result.error_code, result.error_message
    title, text = extract_article_text(result.text)
    return [
        FetchedItem(
            title=title or source.name,
            url=result.final_url or source.url,
            raw_text=text,
            published_at=datetime.now(timezone.utc),
            language=source.language,
        )
    ], "", ""

