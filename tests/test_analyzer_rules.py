from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.analyzer.rules import _age_score, _contains_any, _keyword_hits, calculate_score
from app.models import FetchedItem, Source


def _source(**overrides) -> Source:
    fields = dict(
        name="Test AI Blog", type="rss", url="https://example.com",
        category="ai_lab", tier=1, trust_score=8, language="en",
        rewrite_policy="keep_detailed", enabled=True,
    )
    fields.update(overrides)
    return Source(**fields)


def test_contains_any():
    assert _contains_any("hello world", ["hello"])
    assert not _contains_any("hello world", ["bye"])
    assert _contains_any("Hello World", ["hello"])


def test_keyword_hits():
    assert _keyword_hits("GPT-5 released", ["gpt"])
    assert not _keyword_hits("nothing here", ["gpt"])
    assert _keyword_hits("Multimodal AI model", ["multimodal"])


def test_age_score_recent():
    now = datetime.now(timezone.utc)
    score, reasons, _ = calculate_score(
        FetchedItem(title="test", url="https://x.com", raw_text="x",
                     published_at=now - timedelta(hours=6), language="en"),
        _source(), ["AI", "GPT"], ["release"], now=now,
    )
    assert any("novelty=15" in r for r in reasons)


def test_age_score_old():
    now = datetime.now(timezone.utc)
    score, reasons, _ = calculate_score(
        FetchedItem(title="test", url="https://x.com", raw_text="x",
                     published_at=now - timedelta(days=14), language="en"),
        _source(), ["AI", "GPT"], ["release"], now=now,
    )
    assert any("novelty=0" in r for r in reasons)


def test_calculate_score_relevant_item():
    now = datetime.now(timezone.utc)
    score, _, penalties = calculate_score(
        FetchedItem(
            title="OpenAI Releases GPT-5 with Multimodal Capabilities",
            url="https://example.com/gpt5",
            raw_text="OpenAI has released GPT-5, a new multimodal model that can process text, images, "
            "and audio inputs simultaneously. The model shows significant improvements over GPT-4 in "
            "reasoning, coding, and mathematical benchmarks. It is available via API starting today "
            "for all developers. Early benchmarks show a 40% improvement in reasoning tasks and "
            "significant gains in multimodal understanding across text, images, and audio inputs.",
            published_at=now - timedelta(hours=3), language="en",
        ),
        _source(), ["AI", "GPT", "multimodal", "release"],
        ["release", "launch"], now=now,
    )
    assert score > 60
    assert len(penalties) == 0


def test_calculate_score_promotional():
    now = datetime.now(timezone.utc)
    score, _, penalties = calculate_score(
        FetchedItem(
            title="Best AI Tools 2025", url="https://example.com/promo",
            raw_text="Sponsored post. Save your spot now! Apply now for early bird pricing. "
            "Register today for our AI conference.",
            published_at=now - timedelta(hours=12), language="en",
        ),
        _source(), ["AI"], [], now=now,
    )
    assert any("ad_or_partner_material" in p for p in penalties)


def test_calculate_score_short_item():
    now = datetime.now(timezone.utc)
    score, _, penalties = calculate_score(
        FetchedItem(title="Short", url="https://example.com/short",
                     raw_text="Too short",
                     published_at=now - timedelta(hours=1), language="en"),
        _source(), ["AI"], [], now=now,
    )
    assert any("too_short_without_facts" in p for p in penalties)


def test_calculate_score_no_url():
    now = datetime.now(timezone.utc)
    score, _, penalties = calculate_score(
        FetchedItem(title="No URL Item", url="",
                     raw_text="This is a news item without a proper URL link.",
                     published_at=now - timedelta(hours=2), language="en"),
        _source(), ["AI", "news"], [], now=now,
    )
    assert any("missing_source_url" in p for p in penalties)


def test_calculate_score_clickbait():
    now = datetime.now(timezone.utc)
    score, _, penalties = calculate_score(
        FetchedItem(
            title="СРОЧНО! Эта AI-технология УНИЧТОЖИТ всех!!!",
            url="https://example.com/clickbait",
            raw_text="Some content about AI technology. Nothing new here.",
            published_at=now - timedelta(hours=5), language="ru",
        ),
        _source(), ["AI"], [], now=now,
    )
    assert any("clickbait" in p for p in penalties)


def test_calculate_score_zero():
    now = datetime.now(timezone.utc)
    score, _, _ = calculate_score(
        FetchedItem(title="", url="", raw_text="",
                     published_at=now - timedelta(days=30), language="en"),
        _source(trust_score=0, tier=3), [], [], now=now,
    )
    assert score == 0
