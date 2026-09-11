from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class PipelineReport:
    total_sources: int = 0
    enabled_sources: int = 0
    source_errors: int = 0
    failed_sources: list[str] | None = None
    items_fetched: int = 0
    items_published: int = 0
    items_failed_publish: int = 0
    dry_run: bool = True


def _send_alert(settings: Settings, message: str) -> None:
    if not settings.telegram_bot_token or not settings.admin_chat_id:
        logger.info("admin_chat_id not configured, skipping alert")
        return
    try:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        requests.post(
            url,
            json={"chat_id": settings.admin_chat_id, "text": message, "disable_web_page_preview": False},
            timeout=settings.request_timeout,
        )
    except Exception as exc:
        logger.warning("failed to send alert: %s", exc)


def notify_pipeline_result(settings: Settings, report: PipelineReport) -> None:
    if report.dry_run:
        return
    has_issues = report.source_errors > 0 or report.items_failed_publish > 0
    if not has_issues:
        return
    parts: list[str] = []
    if report.source_errors > 0:
        parts.append(f"⚠️ {report.source_errors}/{report.enabled_sources} источников не загрузились")
        if report.failed_sources:
            parts.append("Проблемные: " + ", ".join(report.failed_sources[:5]))
    if report.items_failed_publish > 0:
        parts.append(f"❌ {report.items_failed_publish} постов не опубликовались")
    if report.items_published > 0:
        parts.append(f"✅ Опубликовано: {report.items_published}")
    if report.items_published == 0 and report.source_errors == report.enabled_sources:
        parts.insert(0, "🚨 Пайплайн не собрал ни одной новости — все источники упали")
    text = "📊 Отчёт ai-news-bot:\n" + "\n".join(parts)
    _send_alert(settings, text)


def notify_critical(settings: Settings, error: str) -> None:
    _send_alert(settings, f"🚨 ai-news-bot: критическая ошибка\n{error}")
