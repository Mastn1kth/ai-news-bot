from __future__ import annotations

import logging

import requests

from app.config import Settings

logger = logging.getLogger(__name__)

CHANNEL_STYLE = (
    "Ты автор русскоязычного Telegram-канала про AI, нейросети, технологии, стартапы и IT-бизнес.\n"
    "Твои посты читают разработчики, продакты и технические специалисты.\n"
    "Пиши живым, информативным языком — как tech-энтузиаст, который разбирается в теме.\n"
    "Не используй канцелярит, не перегружай водой."
)

OUTPUT_FORMAT = (
    "Оформи пост так:\n"
    "1. Заголовок с эмодзи (один-два слова по сути).\n"
    "2. 2-4 абзаца: суть новости, ключевые факты, контекст, почему это важно.\n"
    "3. Если есть цифры, даты, названия моделей, суммы — обязательно укажи их.\n"
    "4. В конце — строка 'Источник: <url>'.\n"
    "Не копируй текст источника дословно. Перескажи своими словами, сохранив смысл и детали.\n"
    "Не добавляй неподтверждённые факты и предположения."
)


def rewrite_with_optional_llm(
    settings: Settings,
    title: str,
    source_text: str,
    source_url: str,
    rule_based_post: str | None = None,
) -> str | None:
    if not settings.use_llm:
        return None

    if settings.llm_provider in {"ollama", "local"}:
        return _rewrite_with_ollama(settings, title, source_text, source_url, rule_based_post)
    if settings.llm_provider in {"openai-compatible", "openai_compatible", "generic"}:
        return _rewrite_with_openai_compatible(settings, title, source_text, source_url, rule_based_post)

    logger.warning("Unknown LLM_PROVIDER=%s, fallback to rule-based post", settings.llm_provider)
    return None


def _build_prompt(title: str, source_text: str, source_url: str, rule_based_post: str | None = None) -> str:
    parts = [
        f"Заголовок: {title}",
        f"URL: {source_url}",
    ]
    if rule_based_post:
        parts.append(f"\nЧерновик (можно улучшить или переписать полностью):\n{rule_based_post[:2000]}")
    parts.append(f"\nТекст источника:\n{source_text[:5000]}")
    return "\n".join(parts)


def _system_prompt() -> str:
    return f"{CHANNEL_STYLE}\n\n{OUTPUT_FORMAT}"


def _normalize_llm_text(text: str, source_url: str) -> str | None:
    text = str(text or "").strip()
    if not text:
        return None
    if source_url not in text:
        text = f"{text[:3700].rstrip()}\n\nИсточник: {source_url}"
    return text[:3900]


def _rewrite_with_ollama(
    settings: Settings,
    title: str,
    source_text: str,
    source_url: str,
    rule_based_post: str | None = None,
) -> str | None:
    ollama_url = settings.llm_api_base or "http://localhost:11434/api/generate"
    try:
        response = requests.post(
            ollama_url,
            json={
                "model": settings.llm_model,
                "system": _system_prompt(),
                "prompt": _build_prompt(title, source_text, source_url, rule_based_post),
                "stream": False,
            },
            timeout=settings.llm_timeout,
        )
        response.raise_for_status()
        data = response.json()
        return _normalize_llm_text(str(data.get("response", "")), source_url)
    except Exception as exc:
        logger.warning("Ollama is unavailable, fallback to rule-based post: %s", exc)
    return None


def _rewrite_with_openai_compatible(
    settings: Settings,
    title: str,
    source_text: str,
    source_url: str,
    rule_based_post: str | None = None,
) -> str | None:
    if not settings.llm_api_base or not settings.llm_model:
        logger.warning("LLM_API_BASE and LLM_MODEL are required for OpenAI-compatible provider")
        return None

    endpoint = settings.llm_api_base.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": _build_prompt(title, source_text, source_url, rule_based_post)},
                ],
                "temperature": 0.3,
            },
            timeout=settings.llm_timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message", {})
        return _normalize_llm_text(str(message.get("content", "")), source_url)
    except Exception as exc:
        logger.warning("OpenAI-compatible LLM is unavailable, fallback to rule-based post: %s", exc)
    return None
