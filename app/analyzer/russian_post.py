from __future__ import annotations

import re

from app.models import FetchedItem, Source
from app.utils.text import normalize_text


MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
GENERIC_ENTITIES = {
    "AI", "API", "RSS", "Atom", "The", "This", "These", "That", "General",
    "Summary", "Article", "Published", "Back", "Share", "Copy", "Mail",
    "LinkedIn", "Facebook", "Here", "Latest",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec",
    "You", "Follow", "Home", "Blog", "News", "Explore", "Sorry",
}
BAD_ENTITY_SUBSTRINGS = (
    "facebook", "linkedin", "copy", "follow", "read ai-generated",
    "ai-generated", "keyword team", "back", "article published",
    "articles", "comments summary", "upvote", "enterprise article",
    "universal cart", "googlebook",
)


def looks_english(text: str) -> bool:
    latin = len(re.findall(r"[A-Za-z]", text or ""))
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", text or ""))
    return latin > cyrillic * 2 and latin > 20


def extract_entities(text: str, limit: int = 12) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"\b[A-Z][A-Za-z0-9.+-]{1,}(?:\s+[A-Z][A-Za-z0-9.+-]{1,}){0,4}\b",
        r"\b(?:GPT|Claude|Gemini|Llama|Mistral|DeepSeek|Nemotron|Copilot|ChatGPT)[A-Za-z0-9 .+-]*\b",
        r"\b[A-Za-z]+(?:AI|ML|GPT)\b",
    ]
    for pattern in patterns:
        candidates.extend(re.findall(pattern, text or ""))

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        clean = normalize_text(candidate).strip(".,:;()[]{}")
        if not clean or clean in GENERIC_ENTITIES:
            continue
        if re.match(rf"^(?:{MONTHS})\s+(?:AI|ML)$", clean, re.IGNORECASE):
            continue
        if any(bad in clean.lower() for bad in BAD_ENTITY_SUBSTRINGS):
            continue
        if len(clean) < 3 or len(clean) > 80:
            continue
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            result.append(clean)
        if len(result) >= limit:
            break
    return result


def extract_numbers_dates(text: str, limit: int = 8) -> list[str]:
    patterns = [
        rf"\b(?:{MONTHS})\s+\d{{1,2}},?\s+\d{{4}}\b",
        rf"\b\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}\b",
        r"\b20\d{2}\b",
        r"\b\d+(?:\.\d+)?\s?(?:B|M|K|million|billion|тыс\.?|млн|млрд|%)\b",
        r"\b\d+(?:\.\d+)?[A-Za-z]*-parameter\b",
        r"\b\d+(?:\.\d+)?B-parameter\b",
        r"\bv?\d+(?:\.\d+){1,3}\b",
    ]
    found: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.findall(pattern, text or "", flags=re.IGNORECASE):
            value = match if isinstance(match, str) else " ".join(match)
            value = normalize_text(value)
            key = value.lower()
            if value and key not in seen:
                seen.add(key)
                found.append(value)
            if len(found) >= limit:
                return found
    return found


def detect_event(text: str) -> tuple[str, str]:
    lowered = (text or "").lower()
    if "recap" in lowered or "latest ai news" in lowered or "updates from" in lowered:
        return "дайджест", "опубликовала дайджест или подборку обновлений"
    checks = [
        (("released", "launch", "launched", "rolled out", "available", "выпуст"), "релиз", "выпустила или запустила обновление"),
        (("announced", "introduced", "unveiled", "представ"), "анонс", "анонсировала или представила новость"),
        (("funding", "raises", "raised", "investment", "инвест"), "инвестиции", "сообщила об инвестициях или финансировании"),
        (("acquires", "acquired", "acquisition", "сделк"), "сделка", "сообщила о сделке или покупке"),
        (("partnership", "partners", "партн"), "партнерство", "объявила о партнерстве"),
        (("lawsuit", "regulation", "ban", "court", "регулир", "запрет"), "регулирование", "связана с регулированием, запретом или судебным спором"),
        (("research", "paper", "benchmark", "study", "исслед"), "исследование", "опубликовала исследование или бенчмарк"),
        (("update", "feature", "preview", "beta", "обнов"), "обновление", "рассказала об обновлении продукта или функции"),
    ]
    for keys, event_type, phrase in checks:
        if any(key in lowered for key in keys):
            return event_type, phrase
    return "новость", "сообщила о событии в сфере AI/IT"


def infer_actor(source: Source, title: str, entities: list[str]) -> str:
    source_map = {
        "OpenAI News": "OpenAI",
        "Google AI Blog": "Google",
        "Google DeepMind Blog": "Google DeepMind",
        "Hugging Face Blog": "Hugging Face",
        "Microsoft AI Blog": "Microsoft",
        "NVIDIA AI Blog": "NVIDIA",
        "Meta AI Blog": "Meta",
        "Anthropic News": "Anthropic",
    }
    if source.name in source_map:
        return source_map[source.name]
    for entity in entities:
        if entity.lower() in (title or "").lower():
            return entity
    return source.name


def build_rule_based_russian_post(item: FetchedItem, source: Source, cleaned_text: str, score: int) -> str:
    title = normalize_text(item.title)
    combined = cleanup_for_fact_extraction(normalize_text(f"{title}. {cleaned_text}"))
    entities = extract_entities(combined)
    facts = extract_numbers_dates(combined, limit=5)
    event_type, event_phrase = detect_event(combined)
    actor = infer_actor(source, title, entities)
    emoji = "🤖" if source.category in {"ai_lab", "open_source_ai", "hardware_ai"} else "🧠"

    ru_title = build_russian_title(emoji, actor, event_type, title, entities)
    body_parts = [f"{actor} {event_phrase}"]

    main_entities = [entity for entity in entities if entity.lower() != actor.lower()][:8]
    if main_entities:
        body_parts.append("Упомянуто: " + ", ".join(main_entities) + ".")
    if facts:
        body_parts.append("Детали: " + ", ".join(facts) + ".")

    detail = build_detail_sentence(source, title, combined, event_type)
    if detail:
        body_parts.append(detail)

    if source.type == "telegram" or source.rewrite_policy == "rewrite_required":
        body_parts.append(
            "Источник — Telegram, поэтому текст не копируется дословно: только смысл, факты и ссылка."
        )

    why = why_it_matters_ru(event_type, combined, score)
    parts = [ru_title, "", " ".join(body_parts)]
    if why:
        parts.extend(["", "Почему это важно:", why])
    parts.extend(["", f"Источник: {item.url}"])
    return "\n".join(parts).strip()[:3900]


def build_russian_title(emoji: str, actor: str, event_type: str, original_title: str, entities: list[str]) -> str:
    lower = original_title.lower()
    if not looks_english(original_title):
        return f"{emoji} {original_title}"
    if "latest ai news" in lower or "ai updates" in lower:
        return f"{emoji} {actor} подвела итоги AI-обновлений"
    target = next((entity for entity in entities if entity.lower() != actor.lower()), "")
    event_titles = {
        "релиз": "выпустила обновление",
        "анонс": "представила новость",
        "инвестиции": "сообщила об инвестициях",
        "сделка": "сообщила о сделке",
        "партнерство": "объявила о партнерстве",
        "регулирование": "попала в регуляторную новость",
        "исследование": "опубликовала исследование",
        "дайджест": "опубликовала дайджест AI-обновлений",
        "обновление": "обновила продукт",
        "новость": "попала в AI/IT-новости",
    }
    action = event_titles.get(event_type, "сообщила новость")
    if target:
        return f"{emoji} {actor} {action}: {target}"
    return f"{emoji} {actor} {action}"


def build_detail_sentence(source: Source, title: str, text: str, event_type: str) -> str:
    lowered = text.lower()
    if "multimodal" in lowered or "мультимод" in lowered:
        return "Отмечается мультимодальность: работа с текстом, изображениями и другими типами данных."
    if "open-source" in lowered or "open source" in lowered or "github" in lowered:
        return "Решение доступно в открытом виде — можно проверить, доработать или использовать в своих проектах."
    if event_type == "исследование":
        return "Такие публикации полезны как сигнал о направлениях исследований и инженерных практик."
    if source.rewrite_policy == "summary_only":
        return "Источник допускает только краткий пересказ."
    return ""


def why_it_matters_ru(event_type: str, text: str, score: int) -> str:
    if score < 70:
        return ""
    lowered = text.lower()
    if event_type in {"релиз", "обновление", "дайджест"}:
        return "Новые модели, API и функции быстро переходят из анонсов в рабочие инструменты для разработчиков, бизнеса и пользователей."
    if event_type == "инвестиции":
        return "Инвестиции показывают, какие направления AI и технологий рынок считает перспективными."
    if event_type == "регулирование":
        return "Регулирование и судебные решения могут менять правила работы для компаний, разработчиков и пользователей."
    if event_type == "исследование":
        return "Исследования и бенчмарки помогают понять реальные ограничения и возможности новых AI-систем."
    if any(key in lowered for key in ["api", "tool", "sdk", "github", "open-source"]):
        return "Практичные инструменты важны тем, что их можно быстро применить в продуктах, автоматизации и разработке."
    return ""


def cleanup_for_fact_extraction(text: str) -> str:
    replacements = [
        "Share x.com Facebook LinkedIn Mail Copy link",
        "Read AI-generated summary",
        "General summary",
        "Summaries were generated by Google AI. Generative AI is experimental.",
        "Back to Articles",
        "Back to articles",
    ]
    cleaned = text
    for value in replacements:
        cleaned = cleaned.replace(value, " ")
    cleaned = re.sub(
        r"\b[A-Z][a-z]+ [A-Z][a-z]+ [a-z0-9_]+ Follow [A-Za-z0-9_]+\b",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"\b(?:Share|Facebook|LinkedIn|Mail|Copy link|Upvote)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
