from __future__ import annotations

from unittest import mock

import requests

from app.publisher import telegram_bot as tb


def test_send_message_no_credentials(settings):
    result = tb.send_message(settings, "test")
    assert not result.success
    assert "required" in result.error_message


def _make_bot_settings(settings):
    return settings.__class__(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_chat_id="-1001234567890",
        admin_chat_id="",
        min_score=settings.min_score,
        max_posts_per_run=settings.max_posts_per_run,
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
        database_path=settings.database_path,
        publish_delay_seconds=0,
        max_items_per_source=5,
    )


def test_send_message_with_credentials(settings):
    bot_settings = _make_bot_settings(settings)
    with mock.patch("app.publisher.telegram_bot.requests.post") as mock_post:
        mock_response = mock.Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.ok = True
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 42}}
        mock_post.return_value = mock_response

        result = tb.send_message(bot_settings, "test message")
        assert result.success
        assert result.message_id == "42"


def test_send_message_api_error(settings):
    bot_settings = _make_bot_settings(settings)
    with mock.patch("app.publisher.telegram_bot.requests.post") as mock_post:
        mock_response = mock.Mock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.json.return_value = {"ok": False, "description": "Forbidden: bot was blocked"}
        mock_post.return_value = mock_response

        result = tb.send_message(bot_settings, "test")
        assert not result.success
        assert "Forbidden" in result.error_message


def test_send_message_network_error(settings):
    bot_settings = _make_bot_settings(settings)
    with mock.patch("app.publisher.telegram_bot.requests.post") as mock_post:
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        result = tb.send_message(bot_settings, "test")
        assert not result.success
        assert "Connection refused" in result.error_message


def test_test_telegram_mocked(settings):
    bot_settings = _make_bot_settings(settings)
    with mock.patch("app.publisher.telegram_bot.send_message") as mock_send:
        mock_send.return_value = tb.PublishResult(True, message_id="1")
        result = tb.test_telegram(bot_settings)
        assert result.success
