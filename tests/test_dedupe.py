from __future__ import annotations

from app.utils.dedupe import extract_simple_entities, is_similar_title, stable_hash, title_hash


def test_stable_hash_consistent():
    assert stable_hash("hello") == stable_hash("hello")
    assert stable_hash("hello") != stable_hash("world")


def test_stable_hash_normalizes():
    h1 = stable_hash("  Hello   World  ")
    h2 = stable_hash("Hello World")
    assert h1 == h2


def test_title_hash():
    h1 = title_hash("GPT-5 Released!")
    h2 = title_hash("gpt-5 released!")
    assert h1 == h2


def test_is_similar_title_exact():
    assert is_similar_title("OpenAI releases GPT-5", "OpenAI releases GPT-5")


def test_is_similar_title_fuzzy():
    assert is_similar_title("OpenAI just released GPT-5", "OpenAI released GPT-5")


def test_is_similar_title_different():
    assert not is_similar_title("OpenAI releases GPT-5", "Microsoft launches Copilot")


def test_is_similar_title_empty():
    assert not is_similar_title("", "something")
    assert not is_similar_title("something", "")


def test_extract_simple_entities():
    entities = extract_simple_entities("OpenAI and Google announced GPT-5")
    assert "OpenAI" in entities
    assert "Google" in entities


def test_extract_simple_entities_empty():
    assert extract_simple_entities("") == set()
    assert extract_simple_entities("lowercase text") == set()
