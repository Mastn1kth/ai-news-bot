from __future__ import annotations

import pytest

from app.main import build_parser


def test_parser_init_db():
    parser = build_parser()
    args = parser.parse_args(["init-db"])
    assert args.command == "init-db"


def test_parser_list_sources():
    parser = build_parser()
    args = parser.parse_args(["list-sources"])
    assert args.command == "list-sources"


def test_parser_dry_run():
    parser = build_parser()
    args = parser.parse_args(["dry-run"])
    assert args.command == "dry-run"


def test_parser_run():
    parser = build_parser()
    args = parser.parse_args(["run"])
    assert args.command == "run"


def test_parser_test_telegram():
    parser = build_parser()
    args = parser.parse_args(["test-telegram"])
    assert args.command == "test-telegram"


def test_parser_validate_sources():
    parser = build_parser()
    args = parser.parse_args(["validate-sources"])
    assert args.command == "validate-sources"


def test_parser_validate_sources_flags():
    parser = build_parser()
    args = parser.parse_args(["validate-sources", "--all", "--write", "--fail-on-error"])
    assert args.all is True
    assert args.write is True
    assert args.fail_on_error is True


def test_parser_verbose():
    parser = build_parser()
    args = parser.parse_args(["--verbose", "dry-run"])
    assert args.verbose is True


def test_parser_no_command():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_retry_failed():
    parser = build_parser()
    args = parser.parse_args(["retry-failed"])
    assert args.command == "retry-failed"
    assert args.max == 10
    assert args.delay == 0


def test_parser_retry_failed_flags():
    parser = build_parser()
    args = parser.parse_args(["retry-failed", "--max", "5", "--delay", "3"])
    assert args.max == 5
    assert args.delay == 3


def test_parser_stats():
    parser = build_parser()
    args = parser.parse_args(["stats"])
    assert args.command == "stats"


def test_utc_now_iso():
    from app.main import utc_now_iso
    result = utc_now_iso()
    assert result.endswith("+00:00") or "+00:00" in result
