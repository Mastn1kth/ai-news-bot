from __future__ import annotations

from pathlib import Path

import pytest

from app.database import (
    connect,
    count_by_status,
    find_duplicate,
    get_failed_items,
    get_publish_stats,
    get_ready_items,
    get_source_health,
    init_database,
    iter_rejected_reasons,
    mark_failed,
    mark_published,
    mark_source_error,
    mark_source_success,
    move_to_ready,
    save_news_item,
    save_publish_log,
)
from app.models import NewsItem


@pytest.fixture
def db_connection(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_database(db_path)
    with connect(db_path) as conn:
        yield conn


def _make_item(**overrides):
    fields = dict(
        source_name="Test Source",
        source_type="rss",
        source_url="https://example.com",
        original_url="https://example.com/article",
        title="Test Article",
        raw_text="Some raw text here",
        cleaned_text="Some cleaned text",
        generated_post="Telegram post content",
        language="en",
        category="ai_lab",
        score=80,
        status="new",
        reject_reason="",
        content_hash="abc123",
        title_hash="def456",
        published_at_source="2025-01-01T00:00:00+00:00",
        found_at="2025-01-01T01:00:00+00:00",
    )
    fields.update(overrides)
    return NewsItem(**fields)


def test_init_database_creates_tables(tmp_path: Path):
    db_path = tmp_path / "fresh.db"
    init_database(db_path)
    with connect(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [row["name"] for row in tables]
        assert "news_items" in names
        assert "sources_state" in names
        assert "publish_log" in names


def test_save_and_find_duplicate(db_connection):
    item = _make_item()
    news_id = save_news_item(db_connection, item)
    assert news_id > 0

    duplicate = find_duplicate(
        db_connection,
        original_url="https://example.com/article",
        title="Test Article",
        content_hash="abc123",
        title_hash="def456",
    )
    assert duplicate == "duplicate"


def test_find_duplicate_similar_title(db_connection):
    item1 = _make_item(status="ready", content_hash="x1", title_hash="y1",
                       original_url="https://example.com/a")
    save_news_item(db_connection, item1)

    duplicate = find_duplicate(
        db_connection,
        original_url="https://example.com/b",
        title="Test Article",  # same normalized title
        content_hash="x2",
        title_hash="y2",
    )
    assert duplicate is not None


def test_get_ready_items_ordered(db_connection):
    for i in range(3):
        item = _make_item(
            title=f"Article {i}",
            score=60 + i * 10,
            status="ready",
            content_hash=f"c{i}",
            title_hash=f"t{i}",
            original_url=f"https://example.com/{i}",
        )
        save_news_item(db_connection, item)

    items = get_ready_items(db_connection, limit=2)
    assert len(items) == 2
    assert items[0]["score"] >= items[1]["score"]


def test_mark_published(db_connection):
    item = _make_item(status="ready")
    news_id = save_news_item(db_connection, item)
    mark_published(db_connection, news_id, "2025-01-01T02:00:00+00:00", "msg_123")

    row = db_connection.execute(
        "SELECT status, telegram_message_id FROM news_items WHERE id = ?",
        (news_id,)
    ).fetchone()
    assert row["status"] == "published"
    assert row["telegram_message_id"] == "msg_123"


def test_mark_failed(db_connection):
    item = _make_item(status="ready")
    news_id = save_news_item(db_connection, item)
    mark_failed(db_connection, news_id, "API error")

    row = db_connection.execute(
        "SELECT status, error_message FROM news_items WHERE id = ?",
        (news_id,)
    ).fetchone()
    assert row["status"] == "failed"
    assert row["error_message"] == "API error"


def test_save_publish_log(db_connection):
    item = _make_item(status="ready")
    news_id = save_news_item(db_connection, item)
    save_publish_log(db_connection, news_id, "2025-01-01T02:00:00+00:00",
                     success=True, telegram_message_id="msg_123")

    row = db_connection.execute(
        "SELECT * FROM publish_log WHERE news_id = ?", (news_id,)
    ).fetchone()
    assert row["success"] == 1
    assert row["telegram_message_id"] == "msg_123"


def test_mark_source_success(db_connection):
    mark_source_success(db_connection, "Test Source", "2025-01-01T01:00:00+00:00")

    row = db_connection.execute(
        "SELECT * FROM sources_state WHERE source_name = ?", ("Test Source",)
    ).fetchone()
    assert row["fail_count"] == 0


def test_mark_source_error(db_connection):
    fail_count = mark_source_error(db_connection, "Test Source",
                                   "2025-01-01T01:00:00+00:00", "connection failed")
    assert fail_count >= 1


def test_count_by_status(db_connection):
    save_news_item(db_connection, _make_item(status="ready"))
    save_news_item(db_connection, _make_item(status="published"))
    save_news_item(db_connection, _make_item(status="rejected"))

    counts = count_by_status(db_connection)
    assert counts.get("ready") == 1
    assert counts.get("published") == 1
    assert counts.get("rejected") == 1


def test_iter_rejected_reasons(db_connection):
    save_news_item(db_connection, _make_item(
        status="rejected", reject_reason="low_score", score=30,
    ))
    save_news_item(db_connection, _make_item(
        status="rejected", reject_reason="duplicate", score=40,
    ))

    reasons = list(iter_rejected_reasons(db_connection, limit=5))
    assert len(reasons) == 2


def test_get_failed_items(db_connection):
    save_news_item(db_connection, _make_item(status="failed", error_message="API error"))
    save_news_item(db_connection, _make_item(status="ready"))
    items = get_failed_items(db_connection, limit=10)
    assert len(items) == 1
    assert items[0]["status"] == "failed"


def test_move_to_ready(db_connection):
    item = _make_item(status="failed", error_message="API error")
    news_id = save_news_item(db_connection, item)
    move_to_ready(db_connection, news_id)
    row = db_connection.execute(
        "SELECT status, error_message FROM news_items WHERE id = ?", (news_id,)
    ).fetchone()
    assert row["status"] == "ready"
    assert row["error_message"] is None


def test_get_source_health(db_connection):
    mark_source_success(db_connection, "Source A", "2025-01-01T01:00:00+00:00")
    mark_source_error(db_connection, "Source B", "2025-01-01T01:00:00+00:00", "fail")
    mark_source_error(db_connection, "Source B", "2025-01-01T02:00:00+00:00", "fail")
    health = get_source_health(db_connection)
    results = {r["source_name"]: int(r["fail_count"]) for r in health}
    assert results.get("Source A") == 0
    assert results.get("Source B") == 2


def test_get_publish_stats(db_connection):
    item = _make_item(status="ready")
    news_id = save_news_item(db_connection, item)
    save_publish_log(db_connection, news_id, "2025-01-01T01:00:00+00:00", success=True)
    save_publish_log(db_connection, news_id, "2025-01-01T02:00:00+00:00", success=False)
    stats = get_publish_stats(db_connection)
    assert stats["total_attempts"] == 2
    assert stats["total_success"] == 1
