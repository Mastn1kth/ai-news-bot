from __future__ import annotations

from unittest.mock import patch

from app.config import Settings
from app.monitor import PipelineReport, notify_pipeline_result


def _settings(**kwargs) -> Settings:
    fields = dict(
        telegram_bot_token="bot:test",
        telegram_chat_id="@channel",
        admin_chat_id="12345",
        min_score=65,
        max_posts_per_run=3,
        dry_run=False,
        request_timeout=15,
        fetch_retries=3,
        use_llm=False,
        llm_provider="ollama",
        llm_api_base="",
        llm_api_key="",
        llm_model="llama3.1",
        llm_timeout=45,
        use_telegram_fetcher=False,
        database_path=":memory:",
        publish_delay_seconds=5,
        max_items_per_source=8,
    )
    fields.update(kwargs)
    return Settings(**fields)


@patch("app.monitor.requests.post")
def test_notify_no_alert_on_dry_run(mock_post):
    report = PipelineReport(source_errors=3, enabled_sources=5, dry_run=True)
    notify_pipeline_result(_settings(), report)
    mock_post.assert_not_called()


@patch("app.monitor.requests.post")
def test_notify_no_alert_no_issues(mock_post):
    report = PipelineReport(source_errors=0, enabled_sources=5, items_published=3, dry_run=False)
    notify_pipeline_result(_settings(), report)
    mock_post.assert_not_called()


@patch("app.monitor.requests.post")
def test_notify_source_errors(mock_post):
    report = PipelineReport(
        source_errors=2, enabled_sources=5, items_published=1, dry_run=False,
        failed_sources=["Test Source A", "Test Source B"],
    )
    notify_pipeline_result(_settings(), report)
    mock_post.assert_called_once()
    args = mock_post.call_args
    assert args[1]["json"]["chat_id"] == "12345"
    assert "2/5" in args[1]["json"]["text"]
    assert "Test Source A" in args[1]["json"]["text"]


@patch("app.monitor.requests.post")
def test_notify_publish_failures(mock_post):
    report = PipelineReport(
        source_errors=0, enabled_sources=5, items_published=0, items_failed_publish=2, dry_run=False,
    )
    notify_pipeline_result(_settings(), report)
    mock_post.assert_called_once()
    assert "2 постов" in mock_post.call_args[1]["json"]["text"]


@patch("app.monitor.requests.post")
def test_notify_critical(mock_post):
    from app.monitor import notify_critical
    notify_critical(_settings(), "All sources failed")
    mock_post.assert_called_once()
    assert "критическая" in mock_post.call_args[1]["json"]["text"]


@patch("app.monitor.requests.post")
def test_notify_no_admin_chat_id(mock_post):
    report = PipelineReport(source_errors=2, enabled_sources=5, dry_run=False)
    notify_pipeline_result(_settings(admin_chat_id=""), report)
    mock_post.assert_not_called()
