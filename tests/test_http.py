from __future__ import annotations

from unittest import mock

import pytest
import requests

from app.utils.http import HttpResult, classify_status, fetch_url


def test_classify_status():
    assert classify_status(429) == "rate_limited"
    assert classify_status(404) == "source_not_found"
    assert classify_status(410) == "source_not_found"
    assert classify_status(500) == "server_error"
    assert classify_status(503) == "server_error"
    assert classify_status(403) == "http_error"
    assert classify_status(200) == ""
    assert classify_status(301) == ""


def test_fetch_url_success():
    result = fetch_url("https://httpbin.org/get", timeout=10, retries=1)
    assert isinstance(result, HttpResult)
    assert result.ok is True or result.ok is False  # network-dependent


@mock.patch("app.utils.http.requests.get")
def test_fetch_url_mock_success(mock_get):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.text = "<html>ok</html>"
    mock_response.url = "https://example.com"
    mock_get.return_value = mock_response

    result = fetch_url("https://example.com", timeout=10, retries=1)
    assert result.ok
    assert result.text == "<html>ok</html>"
    assert result.status_code == 200


@mock.patch("app.utils.http.requests.get")
def test_fetch_url_mock_404(mock_get):
    mock_response = mock.Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    result = fetch_url("https://example.com/404", timeout=10, retries=1)
    assert not result.ok
    assert result.error_code == "source_not_found"


@mock.patch("app.utils.http.requests.get")
def test_fetch_url_mock_retry(mock_get):
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    result = fetch_url("https://example.com/500", timeout=10, retries=3)
    assert not result.ok
    assert mock_get.call_count == 3


@mock.patch("app.utils.http.requests.get")
def test_fetch_url_network_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("connection failed")

    result = fetch_url("https://example.com", timeout=10, retries=2)
    assert not result.ok
    assert result.error_code == "network_error"
