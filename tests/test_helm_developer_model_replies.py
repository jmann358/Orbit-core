"""Malformed provider replies must not crash developer missions or leak details.

All calls are mocked in-process. Nothing reaches a model or real owner data.
"""
import asyncio
import os
from unittest.mock import patch

import httpx
import pytest

from luna.developer_model import AgentModelUnavailable, propose


LOCAL = {
    "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
    "LUNA_MODEL_NAME": "test-coder",
    "LUNA_AGENT_MODEL_ENABLED": "1",
}
GEMINI = {
    "LUNA_MODEL_URL": "https://generativelanguage.googleapis.com/v1beta",
    "LUNA_MODEL_NAME": "test-coder",
    "LUNA_AGENT_MODEL_ENABLED": "1",
    "LUNA_AGENT_ALLOW_CLOUD": "1",
    "LUNA_API_KEY": "REDACT-ME-TEST-SECRET",
}


def _fixture_response(url, payload):
    return httpx.Response(
        200, json=payload, request=httpx.Request("POST", url)
    )


@pytest.mark.parametrize("answer", [
    None, {}, [], 123, "", " \t\n", "\ud800", "\x00",
    "a" * 70001,
])
def test_openai_compatible_invalid_answer_fails_closed_and_can_recover(answer):
    sent = []

    async def fake_post(self, url, **kwargs):
        sent.append((url, kwargs))
        content = answer if len(sent) == 1 else '{"valid": true}'
        return _fixture_response(url, {
            "choices": [{"message": {"content": content}}]
        })

    with patch.dict(os.environ, LOCAL, clear=True):
        with patch.object(httpx.AsyncClient, "post", fake_post):
            with pytest.raises(
                AgentModelUnavailable, match="invalid response"
            ) as error:
                asyncio.run(propose("Return a bounded JSON review proposal"))
            assert "test-coder" not in str(error.value)
            assert asyncio.run(propose("Return a bounded JSON review proposal")) == '{"valid": true}'
    assert len(sent) == 2
    assert all(url == LOCAL["LUNA_MODEL_URL"] + "/chat/completions" for url, _ in sent)
    assert all("Authorization" not in call["headers"] for _, call in sent)


@pytest.mark.parametrize("parts", [
    None, {}, [], [None], ["unexpected"], [{}],
    [{"functionCall": {"name": "action"}}],
    [{"text": 42}], [{"text": None}], [{"text": " \n"}],
    [{"text": "\ud800"}], [{"text": "\x00"}],
    [{"text": "z" * 70001}],
])
def test_gemini_invalid_parts_fail_closed_and_model_can_recover(parts):
    calls = []

    async def fake_post(self, url, **kwargs):
        calls.append((url, kwargs))
        fragments = parts if len(calls) == 1 else [
            {"text": '{"valid": '}, {"text": "true}"},
        ]
        return _fixture_response(url, {
            "candidates": [{"content": {"parts": fragments}}]
        })

    with patch.dict(os.environ, GEMINI, clear=True):
        with patch.object(httpx.AsyncClient, "post", fake_post):
            with pytest.raises(AgentModelUnavailable) as error:
                asyncio.run(propose("Return a bounded JSON review proposal"))
            assert "REDACT-ME-TEST-SECRET" not in str(error.value)
            assert asyncio.run(propose("Return a bounded JSON review proposal")) == '{"valid": true}'
    assert len(calls) == 2
    assert all(url.startswith("https://generativelanguage.googleapis.com/") for url, _ in calls)
    assert all(kwargs["headers"]["x-goog-api-key"] == GEMINI["LUNA_API_KEY"]
               for _, kwargs in calls)


def test_provider_reply_without_expected_wrapper_is_reported_not_executed():
    async def fake_post(self, url, **kwargs):
        return _fixture_response(url, {"choices": ["incorrect"]})

    with patch.dict(os.environ, LOCAL, clear=True):
        with patch.object(httpx.AsyncClient, "post", fake_post):
            with pytest.raises(AgentModelUnavailable, match="request failed"):
                asyncio.run(propose("Propose a review-only change"))


def test_valid_unicode_json_response_is_preserved_without_side_effects():
    answer = '{"summary":"luna \u2600 works","replacement":"pass"}'

    async def fake_post(self, url, **kwargs):
        return _fixture_response(url, {
            "choices": [{"message": {"content": answer}}]
        })

    with patch.dict(os.environ, LOCAL, clear=True):
        with patch.object(httpx.AsyncClient, "post", fake_post):
            assert asyncio.run(propose("Propose a review-only change")) == answer
