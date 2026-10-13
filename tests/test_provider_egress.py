"""Synthetic provider-egress tests: never contact real providers or private data."""
import asyncio

import httpx
import pytest

from luna import core
from luna.model_connection import is_operational_notice
from luna.provider_egress import allowed


ENDPOINT = "https://api.openai.com/v1"
MODEL = "synthetic-model"
SCOPE = ENDPOINT + "|" + MODEL


@pytest.fixture
def cloud_chat(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "DB_PATH", tmp_path / "synthetic.db")
    monkeypatch.setenv("LUNA_MODEL_URL", ENDPOINT)
    monkeypatch.setenv("LUNA_MODEL_NAME", MODEL)
    monkeypatch.setenv("LUNA_API_KEY", "fixture-not-real")
    for key in (
        "LUNA_CLOUD_CHAT_SCOPE", "LUNA_CLOUD_MEMORY_SCOPE",
        "LUNA_CLOUD_NOTES_SCOPE", "LUNA_CLOUD_RECALL_SCOPE"
    ):
        monkeypatch.delenv(key, raising=False)
    core.add_message("test", "user", "Synthetic current question")
    return monkeypatch


def test_provider_and_model_scopes_do_not_inherit_across_destinations():
    env = {"LUNA_CLOUD_CHAT_SCOPE": SCOPE}
    assert allowed(ENDPOINT, MODEL, "current_chat", env)
    assert not allowed(ENDPOINT, "another-model", "current_chat", env)
    assert not allowed("https://api.groq.com/v1", MODEL, "current_chat", env)
    assert not allowed(ENDPOINT, MODEL, "personal_memory", env)
    assert not allowed(ENDPOINT, MODEL, "older_excerpts", env)
    assert allowed("http://127.0.0.1:11434/v1", "local", "current_chat", {})
    assert not allowed("http://192.168.0.5:11434/v1", "local", "current_chat", {})
    with pytest.raises(ValueError):
        allowed(ENDPOINT, MODEL, "unknown", env)


def test_cloud_chat_denied_before_any_network_request(cloud_chat):
    async def forbidden(*args, **kwargs):
        pytest.fail("Cloud request must not be sent without exact scope")
    cloud_chat.setattr(httpx.AsyncClient, "post", forbidden)
    answer = asyncio.run(core.respond("test", "Synthetic current question"))
    assert "Cloud chat sharing is not enabled" in answer
    assert is_operational_notice(answer)


def test_chat_scope_does_not_implicitly_disclose_memories_or_project_notes(cloud_chat):
    cloud_chat.setenv("LUNA_CLOUD_CHAT_SCOPE", SCOPE)
    memory_id = core.add_candidate("SYNTHETIC_PERSONAL_MEMORY_MARKER")
    assert core.review_candidate(memory_id, True)
    note_id = core.add_project_note("SYNTHETIC_PROJECT_NOTE_MARKER")
    assert core.decide_project_note(note_id, "approved")
    captured = []
    async def fake_post(self, url, **kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Synthetic answer"}}]},
            request=httpx.Request("POST", url),
        )
    cloud_chat.setattr(httpx.AsyncClient, "post", fake_post)
    assert asyncio.run(core.respond("test", "Synthetic current question")) == "Synthetic answer"
    assert len(captured) == 1
    assert "Synthetic current question" in str(captured[0])
    assert "SYNTHETIC_PERSONAL_MEMORY_MARKER" not in str(captured[0])
    assert "SYNTHETIC_PROJECT_NOTE_MARKER" not in str(captured[0])

    cloud_chat.setenv("LUNA_CLOUD_MEMORY_SCOPE", SCOPE)
    cloud_chat.setenv("LUNA_CLOUD_NOTES_SCOPE", SCOPE)
    assert asyncio.run(core.respond("test", "Synthetic current question")) == "Synthetic answer"
    assert "SYNTHETIC_PERSONAL_MEMORY_MARKER" in str(captured[-1])
    assert "SYNTHETIC_PROJECT_NOTE_MARKER" in str(captured[-1])


def test_cloud_provider_switch_requires_fresh_chat_scope(cloud_chat):
    cloud_chat.setenv("LUNA_CLOUD_CHAT_SCOPE", SCOPE)
    cloud_chat.setenv("LUNA_MODEL_NAME", "other-model")
    async def forbidden(*args, **kwargs):
        pytest.fail("A different model cannot inherit disclosure permission")
    cloud_chat.setattr(httpx.AsyncClient, "post", forbidden)
    assert "Cloud chat sharing is not enabled" in asyncio.run(
        core.respond("test", "Synthetic current question")
    )
