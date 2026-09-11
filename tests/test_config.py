from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config import _bool_env, _int_env, load_sources, read_keywords


def test_bool_env_true(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "true")
    assert _bool_env("TEST_VAR", False) is True
    monkeypatch.setenv("TEST_VAR", "1")
    assert _bool_env("TEST_VAR", False) is True
    monkeypatch.setenv("TEST_VAR", "yes")
    assert _bool_env("TEST_VAR", False) is True
    monkeypatch.setenv("TEST_VAR", "да")
    assert _bool_env("TEST_VAR", False) is True


def test_bool_env_false(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "false")
    assert _bool_env("TEST_VAR", True) is False


def test_bool_env_default():
    assert _bool_env("NONEXISTENT_VAR_XYZ", True) is True
    assert _bool_env("NONEXISTENT_VAR_XYZ", False) is False


def test_int_env(monkeypatch):
    monkeypatch.setenv("TEST_INT", "42")
    assert _int_env("TEST_INT", 0) == 42


def test_int_env_default():
    assert _int_env("NONEXISTENT_INT", 10) == 10


def test_int_env_invalid(monkeypatch):
    monkeypatch.setenv("TEST_INT", "not_a_number")
    with pytest.raises(ValueError, match="TEST_INT must be an integer"):
        _int_env("TEST_INT", 0)


def test_read_keywords(tmp_path: Path):
    kw_file = tmp_path / "test_keywords.txt"
    kw_file.write_text("AI\nGPT\n# comment\nLLM\n\nClaude\n", encoding="utf-8")
    keywords = read_keywords(kw_file)
    assert keywords == ["AI", "GPT", "LLM", "Claude"]


def test_read_keywords_not_found(tmp_path: Path):
    keywords = read_keywords(tmp_path / "nonexistent.txt")
    assert keywords == []


def test_load_sources(tmp_path: Path):
    sources_file = tmp_path / "sources.yml"
    sources_file.write_text(yaml.safe_dump({
        "sources": [
            {
                "name": "Test Source",
                "type": "rss",
                "url": "https://example.com/feed",
                "category": "ai_lab",
                "tier": 1,
                "trust_score": 8,
                "language": "en",
                "rewrite_policy": "keep_detailed",
                "enabled": True,
            }
        ]
    }, allow_unicode=True), encoding="utf-8")

    sources = load_sources(sources_file)
    assert len(sources) == 1
    assert sources[0].name == "Test Source"
    assert sources[0].type == "rss"
    assert sources[0].tier == 1


def test_load_sources_invalid_type(tmp_path: Path):
    sources_file = tmp_path / "sources.yml"
    sources_file.write_text(yaml.safe_dump({
        "sources": [{"name": "Bad", "type": "unknown", "url": "x", "category": "x",
                      "tier": 1, "trust_score": 1, "language": "en", "rewrite_policy": "keep_detailed", "enabled": True}]
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported type"):
        load_sources(sources_file)


def test_load_sources_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_sources(tmp_path / "nonexistent.yml")
