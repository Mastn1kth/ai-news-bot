from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.analyzer.russian_post import (
    build_rule_based_russian_post,
    build_russian_title,
    cleanup_for_fact_extraction,
    detect_event,
    extract_entities,
    extract_numbers_dates,
    infer_actor,
    looks_english,
    why_it_matters_ru,
)
from app.models import FetchedItem, Source


def test_looks_english():
    assert looks_english("OpenAI releases GPT-5 model")
    assert not looks_english("OpenAI выпустила новую модель")
    assert not looks_english("")


def test_extract_entities():
    text = "OpenAI announced GPT-5 with multimodal capabilities. Google also released Gemini 2.0."
    entities = extract_entities(text)
    assert "OpenAI" in entities
    assert "Google" in entities
    assert len(entities) > 0


def test_extract_entities_empty():
    assert extract_entities("") == []
    assert extract_entities("lowercase only") == []


def test_extract_numbers_dates():
    text = "On January 15, 2025, the company raised $500M at $2B valuation. The GPT-5 model has 1T parameters."
    facts = extract_numbers_dates(text)
    assert any("$500M" in f or "500" in f for f in facts)
    assert len(facts) > 0


def test_detect_event_release():
    event_type, phrase = detect_event("OpenAI released GPT-5 today")
    assert event_type == "релиз"


def test_detect_event_announce():
    event_type, phrase = detect_event("Google announced new features")
    assert event_type == "анонс"


def test_detect_event_funding():
    event_type, phrase = detect_event("Startup raises $100M funding round")
    assert event_type == "инвестиции"


def test_detect_event_research():
    event_type, phrase = detect_event("New research paper published on arXiv")
    assert event_type == "исследование"


def test_detect_event_default():
    event_type, phrase = detect_event("Some random tech content")
    assert event_type == "новость"


def test_infer_actor_by_name():
    source = Source(
        name="OpenAI News", type="rss", url="https://openai.com",
        category="ai_lab", tier=1, trust_score=10, language="en",
        rewrite_policy="keep_detailed", enabled=True,
    )
    assert infer_actor(source, "GPT-5 release", ["GPT-5"]) == "OpenAI"


def test_infer_actor_by_entity():
    source = Source(
        name="Unknown Blog", type="rss", url="https://blog.com",
        category="tech_community", tier=2, trust_score=5, language="en",
        rewrite_policy="keep_detailed", enabled=True,
    )
    assert infer_actor(source, "Meta releases Llama 3", ["Meta", "Llama 3"]) == "Meta"


def test_infer_actor_fallback():
    source = Source(
        name="Some Random Blog", type="rss", url="https://blog.com",
        category="tech_community", tier=2, trust_score=5, language="en",
        rewrite_policy="keep_detailed", enabled=True,
    )
    assert infer_actor(source, "Just some news", []) == "Some Random Blog"


def test_build_russian_title_russian_text():
    title = build_russian_title("🤖", "OpenAI", "релиз",
                                "OpenAI выпустила новую модель", [])
    assert "OpenAI выпустила новую модель" in title


def test_build_russian_title_english():
    title = build_russian_title("🤖", "OpenAI", "релиз",
                                "OpenAI Releases GPT-5", ["GPT-5"])
    assert "OpenAI" in title
    assert "GPT-5" in title or "выпустила" in title


def test_why_it_matters_low_score():
    assert why_it_matters_ru("релиз", "some text", 50) == ""


def test_why_it_matters_high_score():
    result = why_it_matters_ru("релиз", "new model release", 75)
    assert result != ""


def test_why_it_matters_investment():
    result = why_it_matters_ru("инвестиции", "funding round", 80)
    assert "Инвестиции" in result or "инвестиции" in result


def test_cleanup_for_fact_extraction():
    text = "Real content. Read AI-generated summary. More real content."
    cleaned = cleanup_for_fact_extraction(text)
    assert "Real content" in cleaned or "More real content" in cleaned


def test_build_rule_based_russian_post():
    item = FetchedItem(
        title="OpenAI Releases GPT-5",
        url="https://example.com/gpt5",
        raw_text="OpenAI has released GPT-5, a new multimodal model. "
        "It shows improvements in reasoning and coding.",
        published_at=datetime.now(timezone.utc),
        language="en",
    )
    source = Source(
        name="OpenAI News", type="rss", url="https://openai.com",
        category="ai_lab", tier=1, trust_score=10, language="en",
        rewrite_policy="keep_detailed", enabled=True,
    )
    post = build_rule_based_russian_post(item, source, item.raw_text, 85)
    assert len(post) > 50
    assert "Источник:" in post
    assert "https://example.com/gpt5" in post


def test_build_rule_based_russian_post_telegram():
    item = FetchedItem(
        title="Новость из Telegram",
        url="https://t.me/channel/123",
        raw_text="Важная новость про AI от надёжного источника.",
        published_at=datetime.now(timezone.utc),
        language="ru",
    )
    source = Source(
        name="Test Telegram", type="telegram", url="https://t.me/channel",
        category="tech_community", tier=2, trust_score=5, language="ru",
        rewrite_policy="rewrite_required", enabled=True,
    )
    post = build_rule_based_russian_post(item, source, item.raw_text, 80)
    assert "не копируется" in post or "Telegram" in post
