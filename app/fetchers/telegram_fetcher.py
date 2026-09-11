from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import timezone

from app.config import Settings
from app.models import FetchedItem, Source
from app.utils.text import remove_telegram_noise

logger = logging.getLogger(__name__)


def _channel_from_url(url: str) -> str:
    match = re.search(r"t\.me/([^/?]+)", url)
    if not match:
        return url.strip().lstrip("@")
    return match.group(1).strip()


async def _fetch_messages(source: Source, settings: Settings) -> tuple[list[FetchedItem], str, str]:
    try:
        from telethon import TelegramClient
    except ImportError:
        return [], "telethon_not_installed", "Telethon is not installed"

    api_id = os.getenv("TELETHON_API_ID", "").strip()
    api_hash = os.getenv("TELETHON_API_HASH", "").strip()
    session = os.getenv("TELETHON_SESSION", "ai_news_bot").strip()
    if not api_id or not api_hash:
        return [], "telethon_not_configured", "TELETHON_API_ID and TELETHON_API_HASH are required"

    channel = _channel_from_url(source.url)
    client = TelegramClient(session, int(api_id), api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            return [], "telethon_not_authorized", "Telethon session is not authorized"
        messages = await client.get_messages(channel, limit=settings.max_items_per_source)
        fetched: list[FetchedItem] = []
        for message in messages:
            text = remove_telegram_noise(message.message or "")
            if not text:
                continue
            msg_id = str(message.id)
            msg_url = f"https://t.me/{channel}/{msg_id}"
            title = text[:90].rstrip()
            fetched.append(
                FetchedItem(
                    title=title,
                    url=msg_url,
                    raw_text=text,
                    published_at=message.date.astimezone(timezone.utc) if message.date else None,
                    language=source.language,
                    extra={"telegram_channel": channel, "telegram_message_id": msg_id},
                )
            )
        return fetched, "", ""
    finally:
        await client.disconnect()


def fetch_telegram_source(source: Source, settings: Settings) -> tuple[list[FetchedItem], str, str]:
    if not settings.use_telegram_fetcher:
        return [], "", "Telegram fetcher disabled"
    try:
        return asyncio.run(_fetch_messages(source, settings))
    except Exception as exc:
        logger.warning("Telegram fetch failed for %s: %s", source.name, exc)
        return [], "telegram_fetch_error", str(exc)

