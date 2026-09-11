from __future__ import annotations

import logging

from app.utils.logging import SecretFilter, configure_logging, TOKEN_PATTERN


def test_token_pattern_matches():
    assert TOKEN_PATTERN.search("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    assert TOKEN_PATTERN.search("token=987654:Abcdefghijklmnopqrstuvwxyz1234567890-AB")


def test_token_pattern_no_match():
    assert not TOKEN_PATTERN.search("just some text")
    assert not TOKEN_PATTERN.search("short:token")
    assert not TOKEN_PATTERN.search("12345:short")


def test_secret_filter_redacts_message():
    filt = SecretFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0,
                               "token is 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                               None, None)
    filt.filter(record)
    assert "[redacted-token]" in record.msg
    assert "123456:ABC" not in record.msg


def test_secret_filter_redacts_args():
    filt = SecretFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0,
                               "token is %s", ("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",),
                               None)
    filt.filter(record)
    assert "[redacted-token]" in str(record.args)


def test_secret_filter_passes_clean():
    filt = SecretFilter()
    record = logging.LogRecord("test", logging.INFO, "", 0,
                               "clean message", None, None)
    filt.filter(record)
    assert record.msg == "clean message"


def test_configure_logging():
    configure_logging(verbose=True)
    logger = logging.getLogger("test_logger")
    logger.info("test with token 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
