from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class HttpResult:
    ok: bool
    status_code: int | None
    text: str
    final_url: str
    error_code: str
    error_message: str


def classify_status(status_code: int) -> str:
    if status_code == 429:
        return "rate_limited"
    if status_code in {404, 410}:
        return "source_not_found"
    if status_code >= 500:
        return "server_error"
    if status_code >= 400:
        return "http_error"
    return ""


def fetch_url(url: str, *, timeout: int, retries: int, user_agent: str = "ai-news-bot/1.0") -> HttpResult:
    delays = [2, 5, 10]
    headers = {"User-Agent": user_agent}
    last_error = ""
    error_code = "network_error"
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            error_code = classify_status(response.status_code)
            if not error_code:
                return HttpResult(True, response.status_code, response.text, response.url, "", "")
            last_error = f"HTTP {response.status_code}"
            if response.status_code < 500 and response.status_code != 429:
                return HttpResult(False, response.status_code, "", response.url, error_code, last_error)
        except requests.RequestException as exc:
            error_code = "network_error"
            last_error = str(exc)
        if attempt < retries:
            time.sleep(delays[min(attempt - 1, len(delays) - 1)])
    logger.warning("HTTP fetch failed for %s: %s", url, last_error)
    return HttpResult(False, None, "", url, error_code, last_error)
