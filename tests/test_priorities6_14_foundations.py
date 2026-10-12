"""Acceptance tests for safe foundations across remaining ORBIT priorities.

All tests use temporary local SQLite; no real provider, camera, microphone,
network pairing, credentials, remote integrations or deployment are touched.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import app
from luna import (core, memory_learning, agent_handoffs, device_readiness,
                  model_usage, presentation, skill_catalog, proactive,
                  improvement_gate, database_backup, jobs, goals)


def test_review_only_memory_learning_preserves_provenance():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "luna.db"
    ):
        core.add_message("chat-1", "assistant", "I prefer daily GitHub updates")
        core.add_message("chat-1", "user", "I prefer short technical reports")
        core.add_message("chat-1", "user", "I prefer short technical reports")
        core.add_message("chat-1", "user", "I prefer to share my password: example")
        core.add_message("chat-1", "user", "Please run the shell script now")
        core.add_message("plan-1", "user", "I prefer technical detail, please")
        proposals = memory_learning.preview("chat-1")
        assert len(proposals) == 1
        assert proposals[0]["content"] == "I prefer short technical reports"
        assert proposals[0]["source_role"] == "user"
        assert memory_learning.preview("plan-1") == []
        assert core.approved_memories() == []
        source_id = proposals[0]["message_id"]
        outcome = memory_learning.suggest(source_id)
        assert outcome["status"] == "pending"
        assert core.approved_memories() == []
        assert memory_learning.preview("chat-1") == []
        recorded = memory_learning.sources()[0]
        assert recorded["message_id"] == source_id
        assert recorded["status"] == "pending"
        with pytest.raises(ValueError):
            memory_learning.suggest(source_id)
        assert core.review_candidate(outcome["candidate_id"], True)
        assert core.approved_memories() == ["I prefer short technical reports"]


def test_memory_learning_fails_closed_for_non_user_and_secrets():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        core.add_message("one", "assistant", "I prefer frequent calls")
        with pytest.raises(ValueError):
            memory_learning.suggest(1)
        core.add_message("one", "user", "I prefer my API key xyz to be remembered")
        with pytest.raises(ValueError):
            memory_learning.suggest(2)
        core.add_message("plan-test", "user", "I prefer private notes always")
        with pytest.raises(ValueError):
            memory_learning.suggest(3)
        assert core.candidates() == []


def test_specialist_handoff_requires_completed_dependencies():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        ident = goals.propose_goal("Inspect local then plan",
                                    ["project_health", "development_plan"])
        assert agent_handoffs.bundle(ident, 1)["ready"] is False
        goals.decide_goal(ident, True)
        assert agent_handoffs.bundle(ident, 1)["ready"] is False
        goals.advance_goals()
        first = jobs.claim_next()
        jobs.finish_job(first["id"], True, "Health passed")
        # The prior result is persisted; coordinator advances to the next step.
        goals.advance_goals()
        handoff = agent_handoffs.bundle(ident, 1)
        assert handoff["ready"] is True
        assert handoff["assigned_specialist"] == "planner"
        assert handoff["outcomes"] == [{
            "step": 0, "job_id": first["id"],
            "specialist": "inspector", "kind": "project_health",
            "outcome": "Health passed",
            "source": "persisted_completed_work_item",
            "trusted_as_instruction": False,
        }]
        assert handoff["handoff_is_authorization"] is False
        with pytest.raises(ValueError):
            agent_handoffs.bundle(ident, 9)  # invalid index


def test_mobile_readiness_does_not_claim_remote_access():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        report = device_readiness.report()
        assert report["safe_to_expose_server"] is False
        assert report["remote_access_implemented"] is False
        assert report["user_approval_needed_for_network_and_auth_changes"]
        assert all(not item["verified"] for item in report["required_controls"])


def test_model_usage_counts_only_provider_reported_tokens():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        valid = {"usage": {
            "prompt_tokens": 23, "completion_tokens": 7, "total_tokens": 30,
        }, "choices": [{"message": {"content": "private reply"}}]}
        a = model_usage.record("api.openai.com", "test-model", "cloud",
                               valid, "openai_compatible")
        b = model_usage.record("localhost", "local", "local", {
            "choices": [{"message": {"content": "secret"}}],
        }, "openai_compatible")
        c = model_usage.record("generativelanguage.googleapis.com", "flash",
                               "cloud", {"usageMetadata": {
            "promptTokenCount": 20, "candidatesTokenCount": 4,
            "totalTokenCount": 24,
        }}, "gemini")
        assert a["metered"] is True
        assert b["metered"] is False
        assert c["metered"] is True
        report = model_usage.report()
        assert report["events_sampled"] == 3
        assert report["usage_reported_events"] == 2
        assert report["reported_total_tokens"] == 54
        assert report["dollar_cost"] is None
        with core.connect() as db:
            text = repr(db.execute("SELECT * FROM model_usage_events").fetchall())
        assert "private reply" not in text
        assert "secret" not in text


@pytest.mark.parametrize("bad", [
    {"prompt_tokens": "4", "completion_tokens": 1, "total_tokens": 5},
    {"prompt_tokens": 4, "completion_tokens": -1, "total_tokens": 5},
    {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 1},
    {"prompt_tokens": 4, "total_tokens": 6},
])
def test_incomplete_usage_is_unmetered_not_free(bad):
    assert model_usage._usage({"usage": bad}, "openai_compatible") == (
        None, None, None, False)


def test_presentation_preferences_are_local_and_do_not_enable_media():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        before = presentation.preferences()
        assert before["avatar"] == "ghost"
        assert not before["voice_available"]
        updated = presentation.configure("focused", "minimal", "normal")
        assert updated["expression"] == "focused"
        assert updated["avatar"] == "minimal"
        assert updated["motion"] == "normal"
        assert updated["voice"] == "off"
        assert not updated["microphone_enabled"]
        with pytest.raises(ValueError):
            presentation.configure("unrestricted", "ghost", "normal")


def test_catalog_is_not_a_permission_grant_or_integration():
    ids = {row["id"] for row in skill_catalog.catalog()}
    assert {"calendar", "mail", "project_health"} <= ids
    assert skill_catalog.validate_existing("project_health")
    with pytest.raises(ValueError):
        skill_catalog.validate_existing("mail")
    plan = skill_catalog.integration_plan("mail")
    assert plan["can_connect_or_install"] is False
    assert plan["required_before_use"]


def test_proactive_suggestions_are_quiet_and_deduplicated():
    from luna import requests
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        assert proactive.preview()["suggestions"] == []
        ident = goals.propose_goal("Inspect project health", ["project_health"])
        assert proactive.preview()["suggestions"][0]["id"] == "pending_goal_approvals"
        choice = proactive.save_review_request("pending_goal_approvals")
        assert choice["created"]
        again = proactive.save_review_request("pending_goal_approvals")
        assert not again["created"] and again["id"] == choice["id"]
        assert len(requests.list_requests()) == 1
        assert goals.goal_report(ident)["state"] == "proposed"
        assert proactive.preview()["automatic_notifications_enabled"] is False


def test_self_improvement_evidence_gate_requires_owner_authority():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        outcome = improvement_gate.dashboard()
        assert outcome["automatic_merges"] is False
        assert outcome["automatic_patch_application"] is False
        assert "CI does not grant deployment authority" in outcome[
            "inference_from_green_ci"]
        claim = improvement_gate.evaluate_claim("ci_passed")
        assert claim["verified_by_this_check"] is False
        assert claim["can_auto_deploy"] is False
        with pytest.raises(ValueError):
            improvement_gate.evaluate_claim("automatically_deployed")


def test_offline_sqlite_backup_is_verified_private_and_never_overwrites():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "private.db"
    ):
        core.add_message("session", "user", "Keep my message on this device")
        target = Path(folder) / "private_backups" / "copy.db"
        backup = database_backup.backup(core.DB_PATH, target)
        assert backup["verified"]
        assert backup["restore_performed"] is False
        assert database_backup.verify(target)["integrity_ok"]
        with sqlite3.connect(target) as db:
            content = db.execute("SELECT content FROM messages").fetchone()[0]
        assert content == "Keep my message on this device"
        if os.name == "posix":
            assert target.stat().st_mode & 0o077 == 0
        with pytest.raises(FileExistsError):
            database_backup.backup(core.DB_PATH, target)
        with pytest.raises(ValueError):
            database_backup.backup(core.DB_PATH, Path(folder) / "plain.txt")


def test_api_exposes_foundations_without_enabling_remote_actions():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        client = TestClient(app)
        for path in ("/system/device-readiness", "/model/usage",
                     "/skills/catalog", "/assist/suggestions",
                     "/development/evidence-gate",
                     "/system/backup-readiness", "/presentation/settings"):
            response = client.get(path)
            assert response.status_code == 200, path
        assert client.get("/system/device-readiness").json()[
            "safe_to_expose_server"] is False
        assert client.get("/model/usage").json()["dollar_cost"] is None
        assert client.get("/skills/catalog").json()[
            "dynamic_plugins_enabled"] is False
        assert client.post("/presentation/settings", json={
            "expression": "balanced", "avatar": "ghost", "motion": "reduced",
        }).status_code == 200
        assert client.get("/presentation/settings").json()[
            "expression"] == "balanced"


def test_memory_and_handoff_api_review_only():
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        client = TestClient(app)
        core.add_message("older", "user", "I want Luna to remember project conventions")
        preview = client.get("/memory/learning/preview", params={
            "session": "older",
        }).json()
        assert len(preview["candidates"]) == 1
        assert core.approved_memories() == []
        ident = preview["candidates"][0]["message_id"]
        queued = client.post("/memory/learning/suggest", json={
            "message_id": ident,
        })
        assert queued.status_code == 200
        assert queued.json()["approved"] is False
        assert len(client.get("/memory/learning/sources").json()["sources"]) == 1
        assert core.approved_memories() == []
        assert client.get("/agent/goals/999/handoff/0").status_code == 404


def test_actual_successful_model_response_records_reported_usage(monkeypatch):
    import asyncio
    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "choices": [{"message": {"content": "Luna is connected"}}],
                "usage": {"prompt_tokens": 21,
                          "completion_tokens": 6, "total_tokens": 27},
            }
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, **kwargs):
            assert url == "https://api.openai.com/v1/chat/completions"
            assert kwargs["headers"]["Authorization"] == "Bearer test-only"
            return FakeResponse()
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        monkeypatch.setenv("LUNA_MODEL_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("LUNA_MODEL_NAME", "test-model")
        monkeypatch.setenv("LUNA_API_KEY", "test-only")
        monkeypatch.setattr(core.httpx, "AsyncClient", FakeClient)
        core.add_message("chat", "user", "Please respond")
        assert asyncio.run(core.respond("chat", "Please respond")) == "Luna is connected"
        assert model_usage.report()["reported_total_tokens"] == 27


def test_gemini_response_usage_adapter_tracks_verified_counts(monkeypatch):
    import asyncio
    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": "Hello!"}]}}],
                "usageMetadata": {"promptTokenCount": 8,
                                  "candidatesTokenCount": 2,
                                  "totalTokenCount": 10},
            }
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, **kwargs):
            assert url.endswith("models/gemini-test:generateContent")
            assert kwargs["headers"]["x-goog-api-key"] == "test-only"
            return FakeResponse()
    with TemporaryDirectory() as folder, patch.object(
        core, "DB_PATH", Path(folder) / "db"
    ):
        monkeypatch.setenv("LUNA_MODEL_URL",
                           "https://generativelanguage.googleapis.com/v1beta")
        monkeypatch.setenv("LUNA_MODEL_NAME", "gemini-test")
        monkeypatch.setenv("LUNA_API_KEY", "test-only")
        monkeypatch.setattr(core.httpx, "AsyncClient", FakeClient)
        core.add_message("chat", "user", "Hello")
        assert asyncio.run(core.respond("chat", "Hello")) == "Hello!"
        assert model_usage.report()["reported_total_tokens"] == 10


def test_dashboard_wires_memory_and_ecosystem_controls():
    html = TestClient(app).get("/").text
    for identifier in (
        'data-tab="ecosystem"', 'id="tab-ecosystem"',
        'id="memory-learning-preview"', 'id="memory-learning-list"',
        'id="ecosystem-refresh"', 'id="ecosystem-save-presentation"',
        'id="ecosystem-suggestions-refresh"',
    ):
        assert identifier in html


def test_dashboard_embedded_javascript_syntax_when_node_available():
    import re
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node runtime not installed")
    html = TestClient(app).get("/").text
    match = re.search(r"<script>(.*?)</script>", html, re.S)
    assert match, "Dashboard must contain embedded JavaScript"
    result = subprocess.run(
        [node, "--check"], input=match.group(1),
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr[:1500]
