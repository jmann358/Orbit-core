"""Conversation contracts at the provider boundary; no live model requests."""
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core


@pytest.fixture
def conversation(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "DB_PATH", tmp_path / "conversation.db")
    monkeypatch.setenv("LUNA_MODEL_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LUNA_MODEL_NAME", "fixture-model")
    monkeypatch.setenv("LUNA_API_KEY", "fixture-key")
    return TestClient(app)


def provider_json(monkeypatch, payload, status=200):
    async def post(self, url, **kwargs):
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)


@pytest.mark.parametrize("endpoint", [
    "http://localhost:not-a-port/v1",
    "http://localhost:70000/v1",
    "http://[",
    "https://api.groq.com:not-a-port/v1",
    "http://user:private-fixture@localhost:bad/v1",
    "https://untrusted.example/v1",
])
def test_invalid_configuration_returns_notice_without_provider_call(
    conversation, monkeypatch, endpoint
):
    monkeypatch.setenv("LUNA_MODEL_URL", endpoint)

    async def forbidden_post(*args, **kwargs):
        pytest.fail("Invalid configuration must not contact a provider")

    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden_post)
    result = conversation.post("/chat", json={"session": "invalid", "message": "Hello"})
    assert result.status_code == 200
    reply = result.json()["reply"]
    assert reply.startswith("Model endpoint blocked.")
    assert "private-fixture" not in reply and endpoint not in reply
    assert core.history("invalid") == [
        {"role": "user", "content": "Hello"},
        # Connectivity notices are system diagnostics, not model-authored replies.
        {"role": "system", "content": reply},
    ]


@pytest.mark.parametrize("payload", [
    {"choices": [{"message": {"content": content}}]}
    for content in (None, "", " \n\t", "\ud800", 42, [], {"text": "unexpected"})
] + [
    {}, {"choices": []}, {"choices": [{"message": {}}]},
    {"choices": None}, {"choices": [None]},
])
def test_invalid_openai_reply_is_persisted_as_notice_and_next_turn_recovers(
    conversation, monkeypatch, payload
):
    provider_json(monkeypatch, payload)
    failed = conversation.post("/chat", json={"session": "chat", "message": "First turn"})
    assert failed.status_code == 200
    notice = failed.json()["reply"]
    assert notice.startswith("I couldn't reach my configured AI model.")
    assert core.history("chat")[-1] == {"role": "system", "content": notice}
    captured = {}

    async def recovered_post(self, url, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Recovered reply"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", recovered_post)
    recovered = conversation.post("/chat", json={"session": "chat", "message": "Second turn"})
    assert recovered.status_code == 200
    assert recovered.json()["reply"] == "Recovered reply"
    assert all(isinstance(turn["content"], str) and turn["content"].strip()
               for turn in captured["messages"])
    assert all(turn["content"] != notice for turn in captured["messages"])
    assert core.history("chat")[-2:] == [
        {"role": "user", "content": "Second turn"},
        {"role": "assistant", "content": "Recovered reply"},
    ]


@pytest.mark.parametrize("parts", [None, {}, [], [None], ["text"],
    [{"text": None}], [{"text": 12}], [{"text": " \n"}], [{"text": "\ud800"}], [{"functionCall": {}}]])
def test_invalid_gemini_parts_do_not_break_chat(conversation, monkeypatch, parts):
    monkeypatch.setenv("LUNA_MODEL_URL", "https://generativelanguage.googleapis.com/v1beta")
    provider_json(monkeypatch, {"candidates": [{"content": {"parts": parts}}]})
    result = conversation.post("/chat", json={"session": "gemini", "message": "Hello"})
    assert result.status_code == 200
    assert result.json()["reply"].startswith("I couldn't reach my configured AI model.")
    assert len(core.history("gemini")) == 2


@pytest.mark.parametrize("failure", ["timeout", "invalid_url", "invalid_json", 302, 401, 429, 500])
def test_provider_failures_are_safe_notices(conversation, monkeypatch, failure):
    secret_body = "fixture-key PRIVATE_PROVIDER_DETAIL"

    async def failed_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        if failure == "timeout":
            raise httpx.ReadTimeout(secret_body, request=request)
        if failure == "invalid_url":
            raise httpx.InvalidURL(secret_body)
        if failure == "invalid_json":
            return httpx.Response(200, text=secret_body, request=request)
        return httpx.Response(failure, text=secret_body, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", failed_post)
    result = conversation.post("/chat", json={"session": "failures", "message": "Hello"})
    assert result.status_code == 200
    assert result.json()["reply"].startswith("I couldn't reach my configured AI model.")
    with core.connect() as db:
        journal = db.execute("SELECT description FROM improvement_journal").fetchall()
    assert len(journal) == 1
    assert all("fixture-key" not in text and "PRIVATE_PROVIDER_DETAIL" not in text
               for text in [result.text, journal[0][0]])


def test_approved_memory_and_conversation_survive_provider_switch_and_restart(
    conversation, monkeypatch
):
    approved = conversation.post("/memory/candidates", json={"content": "Favorite color is violet"}).json()["id"]
    conversation.post("/memory/candidates", json={"content": "UNAPPROVED_CANDIDATE"})
    assert conversation.post(f"/memory/candidates/{approved}/review?approve=true").status_code == 200
    core.add_message("other", "user", "PRIVATE_OTHER_SESSION")
    captured = []

    async def model_post(self, url, **kwargs):
        captured.append((url, kwargs["json"]))
        if url.endswith("/chat/completions"):
            payload = {"choices": [{"message": {"content": "Violet, from your approved memory."}}]}
        else:
            payload = {"candidates": [{"content": {"parts": [
                {"text": "Still violet. "}, {"text": "Your conversation is here."},
            ]}}]}
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", model_post)
    first = conversation.post("/chat", json={"session": "durable", "message": "What is my favorite color?"})
    assert first.status_code == 200
    assert first.json()["reply"] == "Violet, from your approved memory."
    monkeypatch.setenv("LUNA_MODEL_URL", "https://generativelanguage.googleapis.com/v1beta")
    monkeypatch.setenv("LUNA_MODEL_NAME", "fixture-gemini")
    second = conversation.post("/chat", json={"session": "durable", "message": "Do you still have our conversation?"})
    assert second.status_code == 200
    assert second.json()["reply"] == "Still violet. Your conversation is here."
    assert len(captured) == 2
    first_system = captured[0][1]["messages"][0]["content"]
    second_system = captured[1][1]["systemInstruction"]["parts"][0]["text"]
    for context in (first_system, second_system):
        assert context.startswith(core.SYSTEM)
        assert "Favorite color is violet" in context
        assert "UNAPPROVED_CANDIDATE" not in context
    assert "PRIVATE_OTHER_SESSION" not in json.dumps(captured)
    assert captured[1][1]["contents"][1] == {
        "role": "model", "parts": [{"text": first.json()["reply"]}],
    }
    # A fresh interpreter reopens the real SQLite file, with no provider calls.
    env = dict(os.environ, LUNA_DB_PATH=str(core.DB_PATH))
    probe = subprocess.run([
        sys.executable, "-c",
        "import json; from luna import core; print(json.dumps({'history': core.history('durable'), 'memory': core.approved_memories()}))",
    ], cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=10, check=True)
    reopened = json.loads(probe.stdout)
    assert reopened["history"] == core.history("durable")
    assert len(reopened["history"]) == 4
    assert reopened["memory"] == ["Favorite color is violet"]


def test_unconfigured_model_has_persistent_setup_notice(conversation, monkeypatch):
    monkeypatch.delenv("LUNA_MODEL_URL")
    monkeypatch.delenv("LUNA_MODEL_NAME")

    async def forbidden_post(*args, **kwargs):
        pytest.fail("Unconfigured chat must not call a provider")

    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden_post)
    result = conversation.post("/chat", json={"session": "setup", "message": "Hello"})
    assert result.status_code == 200
    assert result.json()["reply"].startswith("Luna's memory is working, but no AI model is connected yet.")
    assert len(core.history("setup")) == 2
