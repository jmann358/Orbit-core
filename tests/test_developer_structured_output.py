"""Local proposal formatting never replaces validation or expands transport."""
import asyncio
import json

import httpx
import pytest

from luna.developer_agent import proposal_schema, _candidate
from luna.developer_model import propose, AgentModelUnavailable


@pytest.mark.parametrize("endpoint,structured", [
    ("http://127.0.0.1:11434/v1", True),
    ("http://localhost:11434/v1", True),
    ("http://127.0.0.1:1234/v1", False),
    ("https://api.openai.com/v1", False),
])
def test_schema_only_sent_to_local_ollama(monkeypatch, endpoint, structured):
    monkeypatch.setenv("LUNA_AGENT_MODEL_ENABLED", "1")
    monkeypatch.setenv("LUNA_MODEL_URL", endpoint)
    monkeypatch.setenv("LUNA_MODEL_NAME", "test-model")
    monkeypatch.setenv("LUNA_AGENT_ALLOW_CLOUD", "1")
    monkeypatch.setenv("LUNA_API_KEY", "fake")
    captured = []

    async def post(self, url, **kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    schema = proposal_schema("luna/skill_catalog.py", "a" * 64)
    asyncio.run(propose("synthetic source", output_schema=schema))
    assert len(captured) == 1
    assert ("response_format" in captured[0]) is structured
    if structured:
        assert captured[0]["response_format"]["json_schema"]["schema"] == schema
        assert captured[0]["temperature"] == 0


def test_provider_cannot_bypass_revision_check_by_claiming_schema_compliance():
    answer = json.dumps({"path": "luna/skill_catalog.py", "base_sha256": "b" * 64,
                         "replacement": "pass\n", "summary": "synthetic"})
    with pytest.raises(ValueError, match="scoped source revision"):
        _candidate(answer, "luna/skill_catalog.py", "a" * 64)


def test_schema_request_failure_does_not_fallback_or_retry(monkeypatch):
    monkeypatch.setenv("LUNA_AGENT_MODEL_ENABLED", "1")
    monkeypatch.setenv("LUNA_MODEL_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LUNA_MODEL_NAME", "test-model")
    calls = []

    async def post(self, url, **kwargs):
        calls.append(url)
        return httpx.Response(400, text="private provider detail",
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with pytest.raises(AgentModelUnavailable, match="Developer model request failed"):
        asyncio.run(propose("synthetic", output_schema=proposal_schema("x", "a" * 64)))
    assert len(calls) == 1
