from __future__ import annotations

from dataclasses import dataclass

import requests

from app.config import Settings


@dataclass
class PublishResult:
    success: bool
    message_id: str = ""
    error_message: str = ""


def send_message(settings: Settings, text: str) -> PublishResult:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return PublishResult(False, error_message="TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=settings.request_timeout,
        )
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if response.ok and data.get("ok"):
            message = data.get("result", {})
            return PublishResult(True, message_id=str(message.get("message_id", "")))
        description = data.get("description") or f"HTTP {response.status_code}"
        return PublishResult(False, error_message=description)
    except requests.RequestException as exc:
        return PublishResult(False, error_message=str(exc))


def test_telegram(settings: Settings) -> PublishResult:
    return send_message(settings, "Тестовое сообщение от ai-news-bot. Если ты это видишь, Telegram-настройки работают.")

