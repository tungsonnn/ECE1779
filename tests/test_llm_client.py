"""Unit tests for app/services/llm_client.py (no network: the provider is faked)."""

import logging

import httpx
import pytest

from app.services import llm_client

PROMPT = "Hi, I'm <PERSON_1> from <LOCATION_1>"
URL = "https://provider.example/v1/chat/completions"


def use_provider(monkeypatch, handler, url=URL):
    """Point the client at a fake provider. `handler` gets the request and returns the response."""
    sent = {}

    class FakeClient:
        def __init__(self, timeout=None):
            sent["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, post_url, json=None, headers=None):
            sent.update(url=post_url, body=json, headers=headers)
            return handler(httpx.Request("POST", post_url))

    monkeypatch.setattr(llm_client.settings, "llm_url", url)
    monkeypatch.setattr(llm_client.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(llm_client.settings, "llm_model", "test-model")
    monkeypatch.setattr(llm_client.settings, "llm_timeout_seconds", 12.0)
    monkeypatch.setattr(llm_client.httpx, "Client", FakeClient)
    return sent


def answer(text):
    """A provider reply in the OpenAI chat-completions shape."""
    return lambda request: httpx.Response(
        200, request=request, json={"choices": [{"message": {"content": text}}]}
    )


# ------------------------------------------------------------ echo mode


def test_echo_mode_when_no_url_is_set(monkeypatch):
    monkeypatch.setattr(llm_client.settings, "llm_url", "")
    reply = llm_client.complete(PROMPT)

    assert reply.startswith("[echo mode")
    assert PROMPT in reply  # placeholders come back, so restore() still works


# ------------------------------------------------------- the request we send


def test_sends_model_key_timeout_and_the_sanitized_prompt(monkeypatch):
    sent = use_provider(monkeypatch, answer("Hello <PERSON_1>"))

    assert llm_client.complete(PROMPT) == "Hello <PERSON_1>"
    assert sent["url"] == URL
    assert sent["body"]["model"] == "test-model"
    assert sent["headers"]["Authorization"] == "Bearer test-key"
    assert sent["timeout"] == 12.0  # never an unbounded wait
    assert sent["body"]["messages"][-1] == {"role": "user", "content": PROMPT}


def test_system_prompt_tells_the_model_to_keep_placeholders_unchanged(monkeypatch):
    sent = use_provider(monkeypatch, answer("ok"))
    llm_client.complete(PROMPT)

    first = sent["body"]["messages"][0]
    assert first["role"] == "system"
    assert first["content"] == llm_client.SYSTEM_PROMPT
    assert "<PERSON_1>" in first["content"]  # shows the model the exact format
    assert "backslash" in first["content"]  # the failure we saw with the real model
    assert len(sent["body"]["messages"]) == 2  # system, then the user's prompt


# ------------------------------------------------- failures become LLMUnavailable


@pytest.mark.parametrize("status", [401, 404, 429, 500, 503])
def test_error_status_raises_unavailable(monkeypatch, status):
    use_provider(monkeypatch, lambda request: httpx.Response(status, request=request))
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete(PROMPT)


def test_network_failure_raises_unavailable(monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    use_provider(monkeypatch, refuse)
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete(PROMPT)


def test_timeout_raises_unavailable(monkeypatch):
    def slow(request):
        raise httpx.ReadTimeout("too slow", request=request)

    use_provider(monkeypatch, slow)
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete(PROMPT)


@pytest.mark.parametrize(
    "body",
    [
        {},  # no "choices"
        {"choices": []},  # empty list
        {"choices": [{"message": {}}]},  # no "content"
        {"choices": [{"message": {"content": ""}}]},  # empty answer
        {"choices": [{"message": {"content": None}}]},  # not text
    ],
)
def test_unusable_200_answer_raises_unavailable(monkeypatch, body):
    use_provider(monkeypatch, lambda request: httpx.Response(200, request=request, json=body))
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete(PROMPT)


def test_answer_that_is_not_json_raises_unavailable(monkeypatch):
    use_provider(monkeypatch, lambda request: httpx.Response(200, request=request, text="<html>oops</html>"))
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete(PROMPT)


# --------------------------------------------------------------- logging


def test_prompt_reply_and_key_are_never_logged(monkeypatch, caplog):
    use_provider(monkeypatch, answer("Hello <PERSON_1>, a secret reply"))
    with caplog.at_level(logging.DEBUG):
        llm_client.complete(PROMPT)

    assert PROMPT not in caplog.text
    assert "secret reply" not in caplog.text
    assert "test-key" not in caplog.text


def test_failures_are_logged_without_the_prompt_or_the_key(monkeypatch, caplog):
    use_provider(monkeypatch, lambda request: httpx.Response(401, request=request, text=PROMPT))
    with caplog.at_level(logging.DEBUG), pytest.raises(llm_client.LLMUnavailable):
        llm_client.complete(PROMPT)

    assert "401" in caplog.text
    assert PROMPT not in caplog.text
    assert "test-key" not in caplog.text
