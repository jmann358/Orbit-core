"""Evidence for Luna's bounded, independent self-development loop.

Tests use an injected fake model and temporary SQLite/source. No cloud calls,
paid services, host modifications, real GitHub commits, or draft execution.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core
from luna.cloud_worker import claim, connect as job_connect, enqueue, finish, process_one, summary
from luna.developer_agent import (
    MAX_DAILY_CALLS, MAX_ACTIVE, TEMPLATES, list_missions, maybe_queue_automatic,
    mission, queue_mission, run_mission, set_paused, status,
)
from luna.developer_model import configuration, propose


def fixture_source(root):
    target = root / "luna" / "development.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    original = "def safe_check():\n    return 1\n"
    replacement = "def safe_check():\n    return 2\n"
    target.write_text(original, encoding="utf-8")
    return original, replacement


def fake_model_result(original, replacement, path="luna/development.py"):
    return json.dumps({
        "path": path,
        "base_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "replacement": replacement,
        "summary": "Fix the safe diagnostic return value",
    })


def test_agent_is_disabled_without_explicit_model_authorization():
    assert not configuration({})["ready"]
    local = {
        "LUNA_AGENT_MODEL_ENABLED": "1",
        "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
        "LUNA_MODEL_NAME": "local-model",
    }
    assert configuration(local)["ready"]
    cloud = {
        **local, "LUNA_MODEL_URL": "https://api.openai.com/v1",
        "LUNA_API_KEY": "test-key",
    }
    assert not configuration(cloud)["ready"]
    assert configuration({**cloud, "LUNA_AGENT_ALLOW_CLOUD": "1"})["ready"]
    assert not configuration({**cloud, "LUNA_AGENT_ALLOW_CLOUD": "1",
                              "LUNA_MODEL_URL": "http://192.168.1.5/v1"})["ready"]
    assert not configuration({**cloud, "LUNA_AGENT_ALLOW_CLOUD": "1",
                              "LUNA_MODEL_NAME": "../../unsafe"})["ready"]


def test_model_transport_only_sends_agent_source_and_never_chat_memories():
    seen = {}
    async def fake_post(self, url, **kwargs):
        seen["url"] = url
        seen["json"] = kwargs["json"]
        seen["headers"] = kwargs["headers"]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "test draft"}}]},
            request=httpx.Request("POST", url),
        )
    env = {
        "LUNA_AGENT_MODEL_ENABLED": "1",
        "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
        "LUNA_MODEL_NAME": "local-model",
    }
    with patch.dict("os.environ", env, clear=True):
        with patch.object(httpx.AsyncClient, "post", fake_post):
            result = asyncio.run(propose("approved fixture source only"))
    assert result == "test draft"
    assert seen["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert seen["headers"] == {}
    assert seen["json"]["messages"][1]["content"] == "approved fixture source only"
    assert len(seen["json"]["messages"]) == 2


def test_mission_generates_verified_unapplied_replacement_without_touching_source():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        original, replacement = fixture_source(root)
        db = root / "luna.sqlite"
        issued = queue_mission(db, "luna/development.py")
        assert issued["created"]
        ident = issued["mission_id"]
        called = []
        async def model(prompt):
            called.append(prompt)
            return fake_model_result(original, replacement)
        answer = asyncio.run(run_mission(db, ident, model=model, root=root))
        result = mission(db, ident)
        assert "owner review" in answer
        assert len(called) == 1
        assert "Goal:" in called[0]
        assert result["state"] == "review"
        assert result["manifest"]["applied"] is False
        assert result["manifest"]["tests_run"] is False
        assert result["manifest"]["requires_explicit_review"] is True
        assert result["replacement"] == replacement
        assert "-    return 1" in result["diff"]
        assert "+    return 2" in result["diff"]
        assert len(result["fingerprint"]) == 64
        assert (root / "luna/development.py").read_text() == original
        assert status(db)["daily_model_attempts"] == 1


def test_developer_jobs_are_only_claimed_when_model_is_configured():
    env = {
        "LUNA_AGENT_MODEL_ENABLED": "1",
        "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
        "LUNA_MODEL_NAME": "local-model",
    }
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "agent.sqlite"
        ident = queue_mission(db, "luna/development.py")["mission_id"]
        with patch.dict("os.environ", {}, clear=True):
            assert claim(db) is None
        with patch.dict("os.environ", env, clear=True):
            job = claim(db)
            assert job["payload"] == str(ident)
            assert job["kind"] == "development_draft"
            assert finish(db, job["id"], job["attempt"], error="Failed")
            assert summary(db) == {"attention": 1}
            assert claim(db) is None
            assert mission(db, ident)["state"] == "attention"


def test_owner_pause_blocks_new_development_work_but_not_heartbeat():
    env = {
        "LUNA_AGENT_MODEL_ENABLED": "1",
        "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
        "LUNA_MODEL_NAME": "local-model",
    }
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "agent.sqlite"
        queue_mission(db, "luna/development.py")
        enqueue(db, "heartbeat")
        set_paused(db, True)
        with patch.dict("os.environ", env, clear=True):
            first = claim(db)
            assert first["kind"] == "heartbeat"
            assert finish(db, first["id"], first["attempt"], result="alive")
            assert claim(db) is None
            set_paused(db, False)
            assert claim(db)["kind"] == "development_draft"


def test_invalid_model_output_is_never_applied_or_retried():
    env = {
        "LUNA_AGENT_MODEL_ENABLED": "1",
        "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
        "LUNA_MODEL_NAME": "local-model",
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        original, _ = fixture_source(root)
        db = root / "agent.sqlite"
        ident = queue_mission(db, "luna/development.py")["mission_id"]
        async def malicious(_prompt):
            return fake_model_result(
                original,
                "import os\nos.system('echo should_not_run')\n",
                path="app.py",
            )
        def handler(value):
            return asyncio.run(run_mission(db, int(value), model=malicious, root=root))
        with patch.dict("os.environ", env, clear=True):
            finished = process_one(db, {"development_draft": handler})
        assert finished["status"] == "retry_or_attention"
        assert summary(db) == {"attention": 1}
        assert mission(db, ident)["state"] == "attention"
        assert mission(db, ident)["replacement"] == ""
        assert (root / "luna/development.py").read_text() == original
        with job_connect(db) as conn:
            msg = conn.execute("SELECT result FROM cloud_jobs").fetchone()[0]
        assert msg == "Handler failed"


def test_only_allowlisted_targets_and_bounded_missions():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "agent.sqlite"
        with pytest.raises(ValueError):
            queue_mission(db, "app.py")
        first = queue_mission(db, "luna/development.py")
        duplicate = queue_mission(db, "luna/development.py")
        assert duplicate == {"mission_id": first["mission_id"], "created": False}
        second = queue_mission(db, "luna/self_improvement.py")
        assert second["created"]
        assert len(list_missions(db)) == 2
        assert status(db)["counts"]["queued"] == 2


def test_autonomy_requires_explicit_opt_in_and_only_schedules_once_daily():
    day = datetime(2026, 10, 11, tzinfo=timezone.utc)
    env = {
        "LUNA_AGENT_AUTO_ENABLED": "1",
        "LUNA_AGENT_MODEL_ENABLED": "1",
        "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
        "LUNA_MODEL_NAME": "local-model",
    }
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "agent.sqlite"
        assert not maybe_queue_automatic(db, environ={})["queued"]
        one = maybe_queue_automatic(db, environ=env, now=day)
        assert one["queued"]
        two = maybe_queue_automatic(db, environ=env, now=day)
        assert not two["queued"]
        record = mission(db, one["mission_id"])
        assert record["source"] == "automatic"
        assert record["state"] == "queued"
        assert status(db)["daily_model_attempts"] == 0


def test_agent_does_not_exceed_two_model_attempts_per_day():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        original, replacement = fixture_source(root)
        second_path = root / "luna/self_improvement.py"
        second_path.write_text(original)
        db = root / "agent.sqlite"
        calls = []
        async def model(prompt):
            calls.append(prompt)
            target = (
                "luna/self_improvement.py"
                if "Path: luna/self_improvement.py" in prompt
                else "luna/development.py"
            )
            return fake_model_result(original, replacement, target)
        first = queue_mission(db, "luna/development.py")["mission_id"]
        asyncio.run(run_mission(db, first, model=model, root=root))
        second = queue_mission(db, "luna/self_improvement.py")["mission_id"]
        asyncio.run(run_mission(db, second, model=model, root=root))
        third = queue_mission(db, "luna/development.py")["mission_id"]
        with pytest.raises(ValueError):
            asyncio.run(run_mission(db, third, model=model, root=root))
        assert len(calls) == MAX_DAILY_CALLS
        assert mission(db, third)["state"] == "attention"


def test_agent_studio_local_api_status_pause_and_review_page():
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(core, "DB_PATH", Path(directory) / "agent.sqlite"):
            with patch.dict("os.environ", {"LUNA_CLOUD_MODE": "0"}, clear=True):
                client = TestClient(app)
                assert client.get("/agent/studio").status_code == 200
                assert "Luna · Developer Agent" in client.get("/agent/studio").text
                assert client.get("/agent/developer/status").status_code == 200
                invalid = client.post(
                    "/agent/developer/missions", json={"path": "../secrets.env"},
                )
                assert invalid.status_code == 400
                queued = client.post(
                    "/agent/developer/missions",
                    json={"path": "luna/development.py"},
                )
                assert queued.status_code == 200
                ident = queued.json()["mission_id"]
                assert client.get("/agent/developer/missions/"+str(ident)).json()["state"] == "queued"
                assert client.post("/agent/developer/pause",
                                   json={"paused": True}).json()["paused"] is True
                assert client.get("/agent/developer/status").json()["paused"] is True


def test_cloud_gate_also_protects_agent_studio_and_api():
    env = {
        "LUNA_CLOUD_MODE": "1",
        "LUNA_OWNER_TOKEN": "T" * 40,
        "LUNA_PUBLIC_ORIGIN": "https://luna.example.org",
    }
    with patch.dict("os.environ", env, clear=True):
        client = TestClient(app, base_url="https://luna.example.org")
        assert client.get("/agent/studio").status_code == 401
        assert client.get("/agent/developer/status").status_code == 401
        assert client.post("/agent/developer/missions",
                           json={"path": "luna/development.py"}).status_code == 401
