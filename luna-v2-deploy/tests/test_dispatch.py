"""Tests for Luna v2 live dispatch (routing -> real call -> usage accounting).

No network anywhere: the transport is either an in-memory fake or the
Groq HTTP transport with urllib mocked out.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import dispatch as D

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    B.seed_providers(s, OWNER)
    yield s
    s.close()


def fake_transport_factory(calls, text="hello", usage=None):
    """A transport that records (provider, prompt) calls and returns
    canned results; the CLI-style injectable transport."""
    usage = dict(usage or {"requests": 1.0, "tokens": 42.0})

    def fake(provider, prompt):
        calls.append((provider, prompt))
        return text, dict(usage)

    return fake


def usage_rows(s):
    return s._db.execute(
        "SELECT * FROM broker_usage WHERE owner = ?", (OWNER,)).fetchall()


def ledger_rows(s):
    return s.list_ledger(OWNER)


def test_happy_path_records_usage_and_ledger(store):
    calls = []
    result = D.dispatch(store, "say hi", owner=OWNER,
                        needs={"requests": 1, "tokens": 100},
                        transport=fake_transport_factory(calls))
    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-120b"
    assert result.response_text == "hello"
    assert result.usage == {"requests": 1.0, "tokens": 42.0}
    assert calls == [("groq", "say hi")]
    # usage rows exist per unit and carry the owner
    rows = {(r["provider"], r["unit"]): r for r in usage_rows(store)}
    assert rows[("groq", "requests")]["amount"] == 1.0
    assert rows[("groq", "tokens")]["amount"] == 42.0
    # one ledger entry per usage row, always $0
    ledger = ledger_rows(store)
    assert len(ledger) == 2
    assert {e["provider"] for e in ledger} == {"groq"}
    assert all(e["cost_avoided"] == 0.0 for e in ledger)
    # result carries the exact row ids
    assert result.usage_ids["tokens"] == rows[("groq", "tokens")]["id"]
    ledger_ids = {e["id"] for e in ledger}
    assert set(result.ledger_ids.values()) == ledger_ids
    # remaining allocations dropped by exactly what the provider reported
    allocs = {(a.provider, a.unit): a for a in B.list_allocations(store, OWNER)}
    assert allocs[("groq", "tokens")].remaining == 200_000 - 42
    assert allocs[("groq", "requests")].remaining == 1_000 - 1


def test_fail_closed_when_no_provider_covers_needs(store):
    calls = []
    with pytest.raises(B.NoEligibleProvider):
        D.dispatch(store, "say hi", owner=OWNER,
                   needs={"tokens": 10 ** 12},  # nobody has this
                   transport=fake_transport_factory(calls))
    # the transport was never invoked
    assert calls == []
    # and nothing was recorded
    assert usage_rows(store) == []
    assert ledger_rows(store) == []


def test_transport_failure_records_nothing(store):
    calls = []

    def boom(provider, prompt):
        calls.append((provider, prompt))
        raise RuntimeError("provider exploded")

    with pytest.raises(RuntimeError, match="provider exploded"):
        D.dispatch(store, "say hi", owner=OWNER,
                   needs={"requests": 1, "tokens": 100}, transport=boom)
    assert usage_rows(store) == []
    assert ledger_rows(store) == []


def test_unknown_quota_providers_are_never_dispatched(store):
    calls = []
    # gemini and mistral track tokens with unknown quota: even a tiny need
    # must route to groq, never to them
    result = D.dispatch(store, "say hi", owner=OWNER,
                        needs={"tokens": 50},
                        transport=fake_transport_factory(calls))
    assert result.provider == "groq"
    assert calls[0][0] == "groq"
    # and with groq exhausted, the unknown-quota providers still lose
    # (part 1 already consumed 1 request and 42 tokens)
    B.record_usage(store, OWNER, "groq", "requests", 999)
    B.record_usage(store, OWNER, "groq", "tokens", 200_000 - 42)
    calls.clear()
    with pytest.raises(B.NoEligibleProvider):
        D.dispatch(store, "again", owner=OWNER, needs={"tokens": 10},
                   transport=fake_transport_factory(calls))
    assert calls == []


def test_dispatch_without_configured_model_refuses(store):
    # a routable provider with no model on its record cannot dispatch:
    # openrouter (tightest fit here) has no model, so routing succeeds but
    # the call is refused before any transport is invoked
    calls = []
    with pytest.raises(D.DispatchError, match="no dispatch model"):
        D.dispatch(store, "hi", owner=OWNER, needs={"requests": 1},
                   transport=fake_transport_factory(calls))
    assert calls == []
    assert usage_rows(store) == []
    assert ledger_rows(store) == []


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


CANNED = {
    "choices": [{"message": {"content": "hi there"}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 23,
              "total_tokens": 123},
}


def _groq_factory(store):
    return D.make_groq_transport(store, OWNER)


def test_groq_transport_posts_and_maps_usage(store, monkeypatch):
    monkeypatch.setenv(D.GROQ_API_KEY_ENV, "fakekey")
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append(req)
        return FakeResponse(CANNED)

    with patch.object(urllib.request, "urlopen", fake_urlopen):
        text, usage = _groq_factory(store)("groq", "say hi")
    assert text == "hi there"
    assert usage == {"requests": 1.0, "tokens": 123.0}
    assert len(seen) == 1
    req = seen[0]
    assert req.full_url == D.GROQ_CHAT_URL
    # Authorization header present with the fake key, Content-Type is JSON
    hdrs = {k.lower(): v for k, v in req.headers.items()}
    assert hdrs["authorization"] == "Bearer fakekey"
    assert hdrs["content-type"] == "application/json"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["messages"] == [{"role": "user", "content": "say hi"}]


def test_groq_transport_refuses_without_key(store, monkeypatch):
    monkeypatch.delenv(D.GROQ_API_KEY_ENV, raising=False)
    called = []

    def fake_urlopen(req, timeout=None):
        called.append(req)
        return FakeResponse(CANNED)

    with patch.object(urllib.request, "urlopen", fake_urlopen):
        with pytest.raises(D.DispatchError, match="GROQ_API_KEY"):
            _groq_factory(store)("groq", "say hi")
    assert called == []


def test_groq_http_error_becomes_dispatch_error(store, monkeypatch):
    monkeypatch.setenv(D.GROQ_API_KEY_ENV, "fakekey")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests",
                                     {}, None)

    with patch.object(urllib.request, "urlopen", fake_urlopen):
        with pytest.raises(D.DispatchError, match="429"):
            _groq_factory(store)("groq", "say hi")


def test_groq_bad_response_shape_records_nothing(store, monkeypatch):
    monkeypatch.setenv(D.GROQ_API_KEY_ENV, "fakekey")

    def fake_urlopen(req, timeout=None):
        return FakeResponse({"nope": True})

    with patch.object(urllib.request, "urlopen", fake_urlopen):
        with pytest.raises(D.DispatchError):
            D.dispatch(store, "say hi", owner=OWNER,
                       needs={"requests": 1, "tokens": 100},
                       transport=_groq_factory(store))
    assert usage_rows(store) == []
    assert ledger_rows(store) == []


def test_provider_model_comes_from_the_record(store):
    assert D.provider_model(store, OWNER, "groq") == "openai/gpt-oss-120b"
    assert D.provider_model(store, OWNER, "openrouter") is None
    # add_provider stores the model through the record
    B.add_provider(store, OWNER, "newco", "requests", 500, period="daily",
                   model="newco-free-1")
    assert D.provider_model(store, OWNER, "newco") == "newco-free-1"



def _write_helper(tmp_path, body):
    p = tmp_path / "fake_groq_chat.py"
    p.write_text(body)
    return p


def test_connector_transport_maps_response(store, tmp_path):
    helper = _write_helper(tmp_path, (
        "import json, sys\n"
        "prompt = sys.stdin.read()\n"
        "assert prompt == 'hi'\n"
        "assert '--model' in sys.argv\n"
        "print(json.dumps({'choices': [{'message': "
        "{'content': 'via connector'}}], 'usage': {'total_tokens': 77}}))\n"))
    transport = D.make_connector_transport(store, OWNER, helper_path=helper)
    result = D.dispatch(store, "hi", owner=OWNER,
                        needs={"requests": 1.0, "tokens": 100.0},
                        transport=transport)
    assert result.provider == "groq"
    assert result.response_text == "via connector"
    assert result.usage == {"requests": 1.0, "tokens": 77.0}
    assert len(usage_rows(store)) == 2
    assert len(ledger_rows(store)) == 2


def test_connector_transport_failure_records_nothing(store, tmp_path):
    helper = _write_helper(tmp_path, (
        "import sys\n"
        "print('error: Groq HTTP 401: bad key', file=sys.stderr)\n"
        "sys.exit(1)\n"))
    transport = D.make_connector_transport(store, OWNER, helper_path=helper)
    with pytest.raises(D.DispatchError):
        D.dispatch(store, "hi", owner=OWNER,
                   needs={"requests": 1.0, "tokens": 100.0},
                   transport=transport)
    assert usage_rows(store) == []
    assert ledger_rows(store) == []
