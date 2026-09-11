from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import FetchedItem, Source


@pytest.fixture
def sample_source() -> Source:
    return Source(
        name="Test AI Blog",
        type="rss",
        url="https://example.com/feed.xml",
        category="ai_lab",
        tier=1,
        trust_score=8,
        language="en",
        rewrite_policy="keep_detailed",
        enabled=True,
    )


@pytest.fixture
def low_trust_source() -> Source:
    return Source(
        name="Low Trust Blog",
        type="rss",
        url="https://lowtrust.example.com",
        category="tech_community",
        tier=3,
        trust_score=3,
        language="en",
        rewrite_policy="summary_only",
        enabled=True,
    )


@pytest.fixture
def telegram_source() -> Source:
    return Source(
        name="Test Telegram",
        type="telegram",
        url="https://t.me/testchannel",
        category="tech_community",
        tier=2,
        trust_score=5,
        language="ru",
        rewrite_policy="rewrite_required",
        enabled=True,
    )


@pytest.fixture
def sample_item() -> FetchedItem:
    return FetchedItem(
        title="OpenAI Releases GPT-5 with Multimodal Capabilities",
        url="https://example.com/gpt5",
        raw_text="OpenAI has released GPT-5, a new multimodal model that can process text, images, and audio. "
        "The model shows significant improvements over GPT-4 in reasoning and coding benchmarks. "
        "It is available via API starting today.",
        published_at=datetime.now(timezone.utc),
        language="en",
    )


@pytest.fixture
def short_item() -> FetchedItem:
    return FetchedItem(
        title="Short News",
        url="https://example.com/short",
        raw_text="Brief update.",
        published_at=datetime.now(timezone.utc),
        language="en",
    )


@pytest.fixture
def promotional_item() -> FetchedItem:
    return FetchedItem(
        title="Special Offer: AI Tool with 50% Discount",
        url="https://example.com/promo",
        raw_text="This is a sponsored advertisement for an AI tool. Apply now to get early bird pricing. "
        "Save your spot today! Limited time offer with promo code AI50.",
        published_at=datetime.now(timezone.utc),
        language="en",
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        telegram_bot_token="",
        telegram_chat_id="",
        admin_chat_id="",
        min_score=65,
        max_posts_per_run=3,
        dry_run=True,
        request_timeout=15,
        fetch_retries=1,
        use_llm=False,
        llm_provider="ollama",
        llm_api_base="",
        llm_api_key="",
        llm_model="llama3.1",
        llm_timeout=45,
        use_telegram_fetcher=False,
        database_path=Path(":memory:"),
        publish_delay_seconds=0,
        max_items_per_source=5,
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def ai_keywords() -> list[str]:
    return ["AI", "LLM", "GPT", "Claude", "Gemini", "Llama", "Mistral", "DeepSeek",
            "neural network", "machine learning", "multimodal"]


@pytest.fixture
def important_keywords() -> list[str]:
    return ["release", "launch", "announce", "funding", "acquisition",
            "релиз", "запуск", "анонс", "инвестиции"]
