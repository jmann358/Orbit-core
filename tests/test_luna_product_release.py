"""Luna release-path checks: chat, persistence, and model configuration.

No real provider/network calls: simulated OpenAI-compatible responses exercise
the same HTTP adapter, API route, and SQLite history as normal local chat.
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app import app
from luna import core
from luna.model_connection import classify_endpoint, inspect_model_configuration


def test_model_allowlist_blocks_external_http_and_untrusted_cloud():
    assert classify_endpoint("http://127.0.0.1:11434/v1") == "local"
    assert classify_endpoint("http://localhost:1234/v1") == "local"
    assert classify_endpoint("https://api.openai.com/v1") == "cloud"
    assert classify_endpoint("https://generativelanguage.googleapis.com/v1beta/openai") == "cloud"
    for url in (
        "http://192.168.0.5:11434/v1", "http://example.com/v1",
        "https://evil.example/v1", "https://api.openai.com.evil.example/v1",
        "https://user:password@api.openai.com/v1", "https://api.openai.com:8080/v1",
        "https://api.openai.com/v1?api_key=secret", "file:///tmp/model",
        "http://[broken",
    ):
        assert classify_endpoint(url) is None


def test_readiness_hides_secrets_and_never_calls_model():
    env = {
        "LUNA_MODEL_URL": "https://api.openai.com/v1",
        "LUNA_MODEL_NAME": "private-model-name",
        "LUNA_API_KEY": "PRIVATE-KEY-NEVER-SHOW",
    }
    with patch.dict("os.environ", env, clear=True):
        response = TestClient(app).get("/chat/readiness")
        status = response.json()
    assert response.status_code == 200
    assert status["state"] == "configured_unverified"
    assert status["transport"] == "cloud"
    assert status["provider_contacted"] is False
    assert status["remote_device_access"] is False
    assert "PRIVATE-KEY-NEVER-SHOW" not in response.text
    assert "private-model-name" not in response.text
    assert "https://api.openai.com" not in response.text


def test_status_is_clear_when_model_unavailable():
    assert inspect_model_configuration({})["state"] == "not_configured"
    assert inspect_model_configuration({
        "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1", "LUNA_MODEL_NAME": "qwen",
    })["state"] == "configured_unverified"
    assert inspect_model_configuration({
        "LUNA_MODEL_URL": "https://api.openai.com/v1", "LUNA_MODEL_NAME": "gpt",
    })["state"] == "key_required"
    assert inspect_model_configuration({
        "LUNA_MODEL_URL": "https://untrusted.example/v1", "LUNA_MODEL_NAME": "gpt",
        "LUNA_API_KEY": "hidden",
    })["state"] == "blocked"


def test_local_model_chat_survives_new_client_and_keeps_turn_order():
    calls = []

    async def simulated_provider(self, url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Luna reply " + str(len(calls))}}]},
            request=httpx.Request("POST", url),
        )

    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "chat.db"):
            with patch.dict("os.environ", {
                "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
                "LUNA_MODEL_NAME": "local-test-model",
            }, clear=True):
                with patch.object(httpx.AsyncClient, "post", simulated_provider):
                    with TestClient(app) as first_client:
                        first = first_client.post("/chat", json={
                            "session": "release-test", "message": "Hello, Luna",
                        })
                    # A new API client stands in for closing and reopening the app.
                    with TestClient(app) as reopened_client:
                        second = reopened_client.post("/chat", json={
                            "session": "release-test", "message": "Do you remember?",
                        })
                        page = reopened_client.get(
                            "/history/page?session=release-test"
                        ).json()
                        session_names = [s["session"] for s in reopened_client.get("/sessions").json()]
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["reply"] == "Luna reply 1"
    assert second.json()["reply"] == "Luna reply 2"
    assert [turn["role"] for turn in calls[1]["messages"][1:]] == [
        "user", "assistant", "user",
    ]
    assert [(item["role"], item["content"]) for item in page["messages"]] == [
        ("user", "Hello, Luna"), ("assistant", "Luna reply 1"),
        ("user", "Do you remember?"), ("assistant", "Luna reply 2"),
    ]
    assert "release-test" in session_names


def test_default_interface_is_conversation_first_with_send_guard():
    html = TestClient(app).get("/").text
    assert html.count('class="tab-panel active"') == 1
    assert 'id="tab-chat" class="tab-panel active"' in html
    assert "let chatSending=false" in html
    assert "if(chatSending)return;" in html
    assert "/chat/readiness" in html
    assert "Your message may already be saved" in html
