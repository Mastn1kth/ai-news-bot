from __future__ import annotations

from app.utils.text import (
    compact_for_post,
    normalize_text,
    normalize_title,
    remove_telegram_noise,
    strip_html,
    summarize_sentences,
)


def test_strip_html_removes_tags():
    html = "<p>Hello <b>world</b></p>"
    assert strip_html(html) == "Hello world"


def test_strip_html_empty():
    assert strip_html("") == ""
    assert strip_html(None) == ""


def test_strip_html_removes_scripts():
    html = "<script>alert('xss')</script><p>content</p>"
    assert strip_html(html) == "content"


def test_normalize_text():
    assert normalize_text("  hello   world  ") == "hello world"


def test_normalize_text_unescapes():
    assert normalize_text("hello &amp; world") == "hello & world"


def test_normalize_text_non_breaking_space():
    assert normalize_text("hello\u00a0world") == "hello world"


def test_normalize_title():
    result = normalize_title("Hello, World! GPT-5 Launch")
    assert "hello" in result
    assert "world" in result
    assert "gpt-5" in result
    assert "," not in result
    assert "!" not in result


def test_remove_telegram_noise():
    text = "Important message\n\nSubscribe to channel\nMore content\nпромокод SAVE50"
    result = remove_telegram_noise(text)
    assert "Important message" in result
    assert "More content" in result
    assert "Subscribe" not in result
    assert "промокод" not in result


def test_remove_telegram_noise_ad():
    text = "Hello\nРеклама\nWorld"
    result = remove_telegram_noise(text)
    assert "Hello" in result
    assert "World" in result
    assert "реклама" not in result


def test_summarize_sentences_short():
    text = "Short text."
    assert summarize_sentences(text) == "Short text."


def test_summarize_sentences_long():
    text = ". ".join(["Sentence with lots of words in it number " + str(i) for i in range(20)])
    result = summarize_sentences(text, max_chars=200, max_sentences=3)
    assert len(result) <= 200


def test_compact_for_post():
    text = ("This is a long text that goes on and on with sufficient detail to pass the threshold "
            "and make sure the compact function actually truncates the content properly. ") * 200
    result = compact_for_post(text, max_chars=500)
    assert len(result) <= 500
