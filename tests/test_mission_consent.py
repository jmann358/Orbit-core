"""One owner click authorizes ONE review-only development mission, not the model."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core, mission_consent, developer_agent
from luna.cloud_worker import claim, process_one, connect as worker_connect
from luna.developer_model import configuration

CLOUD = {
    "LUNA_MODEL_URL": "https://api.groq.com/openai/v1",
    "LUNA_MODEL_NAME": "openai/gpt-oss-20b",
    "LUNA_API_KEY": "TEST-DONT-LOG-FIXTURE",
}


def test_namespaced_groq_model_is_valid_but_not_blanket_dev_permission():
    assert configuration(CLOUD)["ready"] is False
    assert configuration({**CLOUD,
                          "LUNA_AGENT_MODEL_ENABLED": "1",
                          "LUNA_AGENT_ALLOW_CLOUD": "1"})["ready"]
    assert mission_consent.snapshot(CLOUD)["available"] is True
    assert mission_consent.snapshot(CLOUD)["billing_possible"] is True
    assert not mission_consent.snapshot({**CLOUD, "LUNA_MODEL_NAME": "../../unsafe"})["available"]
    assert not mission_consent.snapshot({**CLOUD, "LUNA_MODEL_URL": "http://192.168.0.4:8000/v1"})["available"]
    assert not mission_consent.snapshot({**CLOUD, "LUNA_API_KEY": ""})["available"]
    assert not mission_consent.snapshot({})["available"]


def test_no_development_claim_until_one_owner_explicitly_approves():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "oneoff.db"
        with patch.object(core, "DB_PATH", db), patch.dict(os.environ, CLOUD, clear=True):
            client = TestClient(app)
            first = developer_agent.queue_mission(db, "luna/development.py")["mission_id"]
            second = developer_agent.queue_mission(db, "luna/presentation.py")["mission_id"]
            assert claim(db) is None
            public = client.get("/agent/self-build/model-consent").json()
            assert public["available_unverified"] and public["provider"] == "api.groq.com"
            assert public["model"] == "openai/gpt-oss-20b"
            assert public["max_model_calls"] == 2
            assert public["may_incur_charges"]
            assert "TEST-DONT-LOG-FIXTURE" not in str(public)
            assert client.post("/agent/self-build/authorize/" + str(first),
                               json={"approve": False}).status_code == 409
            assert claim(db) is None
            allowed = client.post("/agent/self-build/authorize/" + str(first),
                                  json={"approve": True})
            assert allowed.status_code == 200, allowed.text
            assert allowed.json()["max_model_calls"] == 2
            assert not allowed.json()["source_applied"]
            assert not allowed.json()["automatic_future_missions_authorized"]
            assert client.post("/agent/self-build/authorize/" + str(first),
                               json={"approve": True}).status_code == 409
            queued = claim(db)
            assert queued["kind"] == "development_draft"
            assert queued["payload"] == str(first)
            assert claim(db) is None  # second mission has no owner permission
            grant = client.get("/agent/self-build/consent/" + str(first)).json()
            assert grant["recorded"] and grant["used_calls"] == 0
            assert not grant["credentials_stored"]
            assert developer_agent.mission(db, second)["state"] == "queued"


def test_oneoff_model_actually_generates_valid_review_only_code_without_global_flag():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / "luna" / "development.py"
        target.parent.mkdir(parents=True)
        original = "def safe_check():\n    return 1\n"
        candidate = "def safe_check():\n    return 2\n"
        target.write_text(original)
        db = root / "luna.db"
        with patch.object(core, "DB_PATH", db), patch.dict(os.environ, CLOUD, clear=True):
            ident = developer_agent.queue_mission(db, "luna/development.py")["mission_id"]
            mission_consent.authorize(db, ident, approved=True)
            calls = []
            async def mock_post(self, url, **kwargs):
                calls.append({"url": url, "payload": kwargs["json"],
                              "authorization": kwargs["headers"].get("Authorization")})
                answer = json.dumps({
                    "path": "luna/development.py",
                    "base_sha256": hashlib.sha256(original.encode()).hexdigest(),
                    "replacement": candidate,
                    "summary": "Keep the diagnostic simple and return 2",
                })
                return httpx.Response(
                    200, json={"choices": [{"message": {"content": answer}}]},
                    request=httpx.Request("POST", url),
                )

            handler = lambda value: asyncio.run(
                developer_agent.run_mission(db, int(value), root=root))
            with patch.object(httpx.AsyncClient, "post", mock_post):
                report = process_one(db, {"development_draft": handler})
            assert report["status"] == "done"
            item = developer_agent.mission(db, ident)
            assert item["state"] == "review"
            assert item["replacement"] == candidate
            assert item["manifest"]["applied"] is False
            assert item["manifest"]["tests_run"] is False
            assert target.read_text() == original
            assert len(calls) == 1
            assert calls[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"
            assert calls[0]["payload"]["model"] == "openai/gpt-oss-20b"
            assert calls[0]["authorization"] == "Bearer TEST-DONT-LOG-FIXTURE"
            assert "memory_candidates" not in str(calls[0]["payload"])
            assert mission_consent.info(db, ident)["used_calls"] == 1
            with worker_connect(db) as database:
                db_data = str(database.execute(
                    "SELECT endpoint,model,approved_at,expires_at,used_calls "
                    "FROM developer_mission_consents").fetchall())
            assert "TEST-DONT-LOG-FIXTURE" not in db_data
            assert developer_agent.status(db)["daily_model_attempts"] == 1


def test_provider_change_expiry_and_revoke_are_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "local.db"
        with patch.dict(os.environ, CLOUD, clear=True):
            ident = developer_agent.queue_mission(db, "luna/development.py")["mission_id"]
            mission_consent.authorize(db, ident, approved=True)
            with patch.dict(os.environ, {**CLOUD, "LUNA_MODEL_NAME": "other-model"}, clear=True):
                assert not mission_consent.eligible(db, ident)
                assert claim(db) is None
            assert mission_consent.eligible(db, ident)
            mission_consent.revoke(db, ident)
            assert not mission_consent.eligible(db, ident)
            assert claim(db) is None
            with pytest.raises(ValueError):
                mission_consent.authorize(db, ident, approved=True)
            other = developer_agent.queue_mission(db, "luna/self_improvement.py")["mission_id"]
            earlier = datetime.now(timezone.utc) - timedelta(hours=2)
            mission_consent.authorize(db, other, approved=True, now=earlier)
            assert not mission_consent.eligible(db, other)
            assert claim(db) is None


def test_only_explicit_owner_queued_mission_can_get_authorization():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "agents.db"
        with patch.dict(os.environ, CLOUD, clear=True):
            auto = developer_agent.queue_mission(
                db, "luna/development.py", source="automatic")["mission_id"]
            with pytest.raises(ValueError, match="owner"):
                mission_consent.authorize(db, auto, approved=True)
            owner = developer_agent.queue_mission(
                db, "luna/presentation.py", source="owner")["mission_id"]
            developer_agent.set_paused(db, True)
            with pytest.raises(ValueError, match="paused"):
                mission_consent.authorize(db, owner, approved=True)
            developer_agent.set_paused(db, False)
            with pytest.raises(ValueError, match="affirmative"):
                mission_consent.authorize(db, owner, approved=False)
            with pytest.raises(ValueError):
                mission_consent.authorize(db, 9999, approved=True)
            assert mission_consent.info(db, owner)["recorded"] is False


def test_model_call_count_consumed_before_network_and_not_replayed():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "calls.db"
        with patch.dict(os.environ, CLOUD, clear=True):
            ident = developer_agent.queue_mission(db, "luna/development.py")["mission_id"]
            mission_consent.authorize(db, ident, approved=True)
            assert claim(db)["payload"] == str(ident)
            developer_agent._reserve_model_attempt(db, ident)
            assert mission_consent.consume_for_request(db, ident)
            assert mission_consent.consume_for_request(db, ident)
            with pytest.raises(ValueError, match="unavailable|consumed|exhausted"):
                mission_consent.consume_for_request(db, ident)
            assert mission_consent.info(db, ident)["used_calls"] == 2
            with pytest.raises(ValueError):
                mission_consent.revoke(db, ident)


def test_unauthenticated_cloud_cannot_grant_model_spend():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "cloud.db"
        env = {**CLOUD, "LUNA_CLOUD_MODE": "1",
               "LUNA_OWNER_TOKEN": "Q" * 40,
               "LUNA_PUBLIC_ORIGIN": "https://luna.example.org"}
        with patch.object(core, "DB_PATH", db), patch.dict(os.environ, env, clear=True):
            client = TestClient(app, base_url="https://luna.example.org")
            queued = developer_agent.queue_mission(db, "luna/development.py")["mission_id"]
            denied = client.post("/agent/self-build/authorize/" + str(queued),
                                 json={"approve": True})
            assert denied.status_code == 401
            assert mission_consent.info(db, queued)["recorded"] is False
            # Cross-site write denied even with an owner token.
            cross = client.post("/agent/self-build/authorize/" + str(queued),
                                headers={"Authorization": "Bearer " + env["LUNA_OWNER_TOKEN"],
                                         "Origin": "https://evil.example"},
                                json={"approve": True})
            assert cross.status_code == 403
            assert mission_consent.info(db, queued)["recorded"] is False


def test_js_approval_buttons_are_real_events_when_node_available():
    node = shutil.which("node")
    if not node:
        pytest.skip("No Node executable")
    response = TestClient(app).get("/agent/studio")
    assert response.status_code == 200
    assert "Approve 1 AI draft" in response.text
    assert "window.confirm" in response.text
    scripts = re.findall(r"<script>(.*?)</script>", response.text, re.S)
    assert scripts
    for js in scripts:
        checked = subprocess.run([node, "--check"], input=js,
                                 capture_output=True, text=True, timeout=10)
        assert checked.returncode == 0, checked.stderr[:900]
