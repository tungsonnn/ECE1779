"""Unit tests for app/services/pii.py (no Presidio needed: its answers are faked)."""

import logging
import re

import httpx
import pytest

from app.services import pii

TEXT = "Hi, I'm John Smith, email john@gmail.com, phone 416-555-1234"


def finding(entity, start, end, score):
    return {"entity_type": entity, "start": start, "end": end, "score": score}


def fake_presidio(monkeypatch, findings):
    """Make scrub() see `findings` instead of calling the real analyzer."""
    monkeypatch.setattr(pii, "_analyze", lambda text: findings)


# ---------------------------------------------------------------- scrub()


def test_scrub_replaces_each_entity_with_numbered_placeholder(monkeypatch):
    # The exact answer the real Presidio gave for this message.
    fake_presidio(
        monkeypatch,
        [
            finding("EMAIL_ADDRESS", 26, 40, 1.0),
            finding("PERSON", 8, 18, 0.85),
            finding("PHONE_NUMBER", 48, 60, 0.75),
        ],
    )
    sanitized, mapping, counts = pii.scrub(TEXT)

    assert sanitized == "Hi, I'm <PERSON_1>, email <EMAIL_ADDRESS_1>, phone <PHONE_NUMBER_1>"
    assert mapping == {
        "<PERSON_1>": "John Smith",
        "<EMAIL_ADDRESS_1>": "john@gmail.com",
        "<PHONE_NUMBER_1>": "416-555-1234",
    }
    assert counts == {"PERSON": 1, "EMAIL_ADDRESS": 1, "PHONE_NUMBER": 1}


def test_same_value_gets_same_placeholder_and_different_values_get_new_numbers(monkeypatch):
    text = "John Smith emailed Mary Lee. Please reply to John Smith."
    fake_presidio(
        monkeypatch,
        [
            finding("PERSON", 0, 10, 0.85),  # John Smith
            finding("PERSON", 19, 27, 0.85),  # Mary Lee
            finding("PERSON", 45, 55, 0.85),  # John Smith again
        ],
    )
    sanitized, mapping, counts = pii.scrub(text)

    assert sanitized == "<PERSON_1> emailed <PERSON_2>. Please reply to <PERSON_1>."
    assert mapping == {"<PERSON_1>": "John Smith", "<PERSON_2>": "Mary Lee"}
    assert counts == {"PERSON": 3}  # every occurrence is counted for the audit row


def test_overlapping_findings_keep_the_most_confident(monkeypatch):
    # "john" inside the email is also flagged as a PERSON with a lower score.
    text = "Contact john@gmail.com today"
    fake_presidio(
        monkeypatch,
        [
            finding("PERSON", 8, 12, 0.6),
            finding("EMAIL_ADDRESS", 8, 22, 1.0),
        ],
    )
    sanitized, _, counts = pii.scrub(text)

    assert sanitized == "Contact <EMAIL_ADDRESS_1> today"
    assert counts == {"EMAIL_ADDRESS": 1}


def test_entity_types_we_did_not_ask_for_are_ignored(monkeypatch):
    # Presidio's URL finding inside an email (seen in our local test) is not in scope.
    fake_presidio(
        monkeypatch,
        [
            finding("EMAIL_ADDRESS", 26, 40, 1.0),
            finding("URL", 31, 40, 0.5),
        ],
    )
    sanitized, _, counts = pii.scrub(TEXT)

    assert "<EMAIL_ADDRESS_1>" in sanitized
    assert "URL" not in counts


def test_placeholder_typed_by_user_is_never_reused(monkeypatch):
    text = "Ask <PERSON_1> about Jane Doe"
    fake_presidio(monkeypatch, [finding("PERSON", 21, 29, 0.85)])
    sanitized, mapping, _ = pii.scrub(text)

    assert sanitized == "Ask <PERSON_1> about <PERSON_2>"
    assert mapping == {"<PERSON_2>": "Jane Doe"}
    assert pii.restore(sanitized, mapping) == text


def test_no_pii_returns_text_unchanged(monkeypatch):
    fake_presidio(monkeypatch, [])
    assert pii.scrub("How do I sort a list in Python?") == (
        "How do I sort a list in Python?",
        {},
        {},
    )


def test_empty_text_does_not_call_presidio(monkeypatch):
    def boom(text):
        raise AssertionError("Presidio should not be called for empty text")

    monkeypatch.setattr(pii, "_analyze", boom)
    assert pii.scrub("") == ("", {}, {})


def test_scrub_then_restore_gives_back_the_original(monkeypatch):
    fake_presidio(
        monkeypatch,
        [
            finding("EMAIL_ADDRESS", 26, 40, 1.0),
            finding("PERSON", 8, 18, 0.85),
            finding("PHONE_NUMBER", 48, 60, 0.75),
        ],
    )
    sanitized, mapping, _ = pii.scrub(TEXT)
    assert pii.restore(sanitized, mapping) == TEXT


# ------------------------------------------------- talking to Presidio (fail closed)


def test_presidio_unreachable_raises_unavailable(monkeypatch):
    def refuse(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(pii.httpx, "post", refuse)
    with pytest.raises(pii.PIIDetectionUnavailable):
        pii.scrub(TEXT)


def test_presidio_timeout_raises_unavailable(monkeypatch):
    def slow(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(pii.httpx, "post", slow)
    with pytest.raises(pii.PIIDetectionUnavailable):
        pii.scrub(TEXT)


def test_presidio_error_status_raises_unavailable(monkeypatch):
    def server_error(url, **kwargs):
        return httpx.Response(500, request=httpx.Request("POST", url), text="boom")

    monkeypatch.setattr(pii.httpx, "post", server_error)
    with pytest.raises(pii.PIIDetectionUnavailable):
        pii.scrub(TEXT)


def test_presidio_unexpected_answer_raises_unavailable(monkeypatch):
    def weird(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("POST", url), json={"oops": True})

    monkeypatch.setattr(pii.httpx, "post", weird)
    with pytest.raises(pii.PIIDetectionUnavailable):
        pii.scrub(TEXT)


def test_request_asks_only_for_our_entities_and_sends_the_api_key_detector(monkeypatch):
    sent = {}

    def capture(url, json=None, timeout=None):
        sent.update(url=url, body=json, timeout=timeout)
        return httpx.Response(200, request=httpx.Request("POST", url), json=[])

    monkeypatch.setattr(pii.httpx, "post", capture)
    pii.scrub(TEXT)

    assert sent["url"].endswith("/analyze")
    assert sent["body"]["entities"] == pii.ENTITIES
    assert sent["body"]["ad_hoc_recognizers"] == [pii.API_KEY_RECOGNIZER]
    assert sent["timeout"] == pii.PRESIDIO_TIMEOUT_SECONDS


# --------------------------------------------------------- API-key patterns


@pytest.mark.parametrize(
    "key",
    [
        "sk-live-9f8a7b6c5d4e3f2a1b0c",
        "sk-proj-AbCdEfGhIjKlMnOpQrStUvWx",
        "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8",
        "AKIAIOSFODNN7EXAMPLE",
    ],
)
def test_api_key_patterns_match_real_looking_keys(key):
    patterns = [p["regex"] for p in pii.API_KEY_RECOGNIZER["patterns"]]
    assert any(re.search(p, f"my key is {key} thanks") for p in patterns)


@pytest.mark.parametrize("text", ["I use sk-learn for ML", "ghp_short", "AKIA123"])
def test_api_key_patterns_ignore_ordinary_text(text):
    patterns = [p["regex"] for p in pii.API_KEY_RECOGNIZER["patterns"]]
    assert not any(re.search(p, text) for p in patterns)


# --------------------------------------------------------------- restore()


def test_restore_puts_every_value_back_including_repeats():
    mapping = {"<PERSON_1>": "John Smith", "<PERSON_2>": "Mary Lee"}
    reply = "Dear <PERSON_1> and <PERSON_2>, thanks <PERSON_1>!"
    assert pii.restore(reply, mapping) == "Dear John Smith and Mary Lee, thanks John Smith!"


def test_restore_leaves_unknown_placeholders_and_logs_them(caplog):
    mapping = {"<PERSON_1>": "John Smith"}
    with caplog.at_level(logging.WARNING):
        result = pii.restore("Hi <PERSON_1> and <PERSON_3>", mapping)

    assert result == "Hi John Smith and <PERSON_3>"  # never guesses a value
    assert "<PERSON_3>" in caplog.text
    assert "John Smith" not in caplog.text  # real values never logged


def test_restore_ignores_changed_placeholders():
    # If the model rewrites a placeholder, we cannot be sure what it meant, so it stays.
    assert pii.restore("Hi Person 1", {"<PERSON_1>": "John"}) == "Hi Person 1"


def test_restore_with_no_placeholders_is_unchanged():
    assert pii.restore("All good!", {}) == "All good!"
