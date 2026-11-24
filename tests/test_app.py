"""Crucial behaviour of the HTTP app and the request pipeline.

No Postgres, Presidio, or LLM needed: each service call is replaced with a fake.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.schemas import Tenant
from app.services import audit, auth, llm_client, pii

client = TestClient(main.app)
HEADERS = {"X-API-Key": "demo-key-a"}


@pytest.fixture
def fakes(monkeypatch):
    """Healthy fakes for every dependency; tests break one at a time."""
    calls = {"llm_prompts": [], "pending": [], "completed": []}

    def fake_scrub(text):
        return (
            text.replace("Jane", "<PERSON_1>"),
            {"<PERSON_1>": "Jane"},
            {"PERSON": 1},
        )

    def fake_llm(prompt):
        calls["llm_prompts"].append(prompt)
        return f"Reply to {prompt}"

    def fake_auth(api_key):
        # Independent of the real lookup (demo keys now, database later).
        if api_key != HEADERS["X-API-Key"]:
            raise HTTPException(401, "Invalid API key")
        return Tenant(id=1, name="Test Team")

    monkeypatch.setattr(auth, "authenticate", fake_auth)
    monkeypatch.setattr(auth, "check_rate_limit", lambda tenant: None)
    monkeypatch.setattr(pii, "scrub", fake_scrub)
    monkeypatch.setattr(llm_client, "complete", fake_llm)
    monkeypatch.setattr(
        audit, "insert_pending", lambda rid, tid: calls["pending"].append(tid)
    )
    monkeypatch.setattr(
        audit, "complete_row", lambda *args, **kw: calls["completed"].append(args)
    )
    return calls


# ------------------------------------------------------------ health


def test_liveness_always_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {}}


def test_deep_health_503_when_a_dependency_is_down(monkeypatch):
    monkeypatch.setattr(main.health_checks, "check_database", lambda: "down")
    monkeypatch.setattr(main.health_checks, "check_pii_analyzer", lambda: "ok")
    r = client.get("/health/deep")
    assert r.status_code == 503
    assert r.json()["checks"]["database"] == "down"


def test_deep_health_200_when_all_ok(monkeypatch):
    monkeypatch.setattr(main.health_checks, "check_database", lambda: "ok")
    monkeypatch.setattr(main.health_checks, "check_pii_analyzer", lambda: "ok")
    assert client.get("/health/deep").status_code == 200


# ------------------------------------------------------------ pipeline


def test_missing_api_key_is_401(fakes):
    r = client.post("/v1/chat", json={"prompt": "hi"})
    assert r.status_code == 401
    assert fakes["llm_prompts"] == []


def test_llm_sees_placeholders_and_user_gets_real_values(fakes):
    r = client.post("/v1/chat", json={"prompt": "Email Jane"}, headers=HEADERS)
    assert r.status_code == 200
    assert fakes["llm_prompts"] == ["Email <PERSON_1>"]  # PII never left
    assert r.json()["reply"] == "Reply to Email Jane"  # restored for the user
    assert fakes["pending"] == [1] and len(fakes["completed"]) == 1


def test_audit_row_never_contains_the_prompt(fakes):
    client.post("/v1/chat", json={"prompt": "Email Jane"}, headers=HEADERS)
    for args in fakes["completed"]:
        assert not any("Jane" in str(a) for a in args)


def test_fail_closed_when_pii_detection_is_down(fakes, monkeypatch):
    def broken(text):
        raise pii.PIIDetectionUnavailable("analyzer down")

    monkeypatch.setattr(pii, "scrub", broken)
    r = client.post("/v1/chat", json={"prompt": "Email Jane"}, headers=HEADERS)
    assert r.status_code == 503
    assert fakes["llm_prompts"] == []  # unscanned text was not sent


def test_fail_closed_when_audit_is_down(fakes, monkeypatch):
    def broken(rid, tid):
        raise audit.AuditUnavailable("db down")

    monkeypatch.setattr(audit, "insert_pending", broken)
    r = client.post("/v1/chat", json={"prompt": "Email Jane"}, headers=HEADERS)
    assert r.status_code == 503
    assert fakes["llm_prompts"] == []  # unrecorded text was not sent


def test_llm_failure_is_502_and_audit_row_is_closed(fakes, monkeypatch):
    def broken(prompt):
        raise llm_client.LLMUnavailable("provider down")

    monkeypatch.setattr(llm_client, "complete", broken)
    r = client.post("/v1/chat", json={"prompt": "Email Jane"}, headers=HEADERS)
    assert r.status_code == 502
    status, error_code = fakes["completed"][0][1], fakes["completed"][0][4]
    assert (status, error_code) == ("error", "llm_error")
