"""Regression tests: Luna turns action requests into durable tools, not prose."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core, jobs, chat_workflows, developer_agent, self_build


def _client(path):
    return patch.object(core, "DB_PATH", Path(path))


def test_user_verbatim_improve_request_enqueues_real_work_without_model():
    with tempfile.TemporaryDirectory() as directory:
        with _client(Path(directory) / "luna.db"), patch.dict(os.environ, {}, clear=True):
            client = TestClient(app)
            response = client.post("/chat", json={
                "session": "wants-autonomy",
                "message": "I need you to begin improving yourself",
            })
            assert response.status_code == 200
            body = response.json()
            assert body["kind"] == "queued_task"
            assert body["mission_id"] >= 1
            assert body["job_id"] >= 1
            assert "development mission #" in body["reply"]
            assert "BLOCKED" in body["reply"]
            assert "review-only" in body["reply"]
            assert "No code" not in body["reply"] or "not an installed" in body["reply"]
            assert jobs.get_job(body["job_id"])["kind"] == "project_health"
            assert jobs.get_job(body["job_id"])["state"] == "queued"
            assert developer_agent.mission(core.DB_PATH, body["mission_id"])["state"] == "queued"
            assert any(row["id"] == body["mission_id"] for row in
                       developer_agent.list_missions(core.DB_PATH))
            assert core.history("wants-autonomy") == [
                {"role": "user", "content": "I need you to begin improving yourself"},
                {"role": "assistant", "content": body["reply"]},
            ]
            # Responding 'yes' after a real receipt is a read-only status check.
            confirmed = client.post("/chat", json={
                "session": "wants-autonomy", "message": "yes lets do it",
            }).json()
            assert confirmed["kind"] == "work_status"
            assert "Mission #" in confirmed["reply"]
            assert "queued" in confirmed["reply"]
            assert len(jobs.list_jobs()) == 1
            assert len(developer_agent.list_missions(core.DB_PATH)) == 1


def test_duplicate_self_improvement_commands_reuse_queued_work():
    with tempfile.TemporaryDirectory() as directory:
        with _client(Path(directory) / "luna.db"), patch.dict(os.environ, {}, clear=True):
            client = TestClient(app)
            first = client.post("/chat", json={
                "session": "s", "message": "Luna, begin improving yourself."
            }).json()
            second = client.post("/chat", json={
                "session": "s", "message": "I need you to begin improving yourself."
            }).json()
            assert first["mission_id"] == second["mission_id"]
            assert first["job_id"] == second["job_id"]
            assert len(jobs.list_jobs()) == 1
            assert len(developer_agent.list_missions(core.DB_PATH)) == 1
            assert "reused" in second["reply"]


def test_generic_yes_after_model_promise_does_not_create_or_claim_tasks():
    with tempfile.TemporaryDirectory() as directory:
        with _client(Path(directory) / "luna.db"), patch.dict(os.environ, {}, clear=True):
            core.add_message("old-chat", "user", "Could you improve yourself?")
            core.add_message("old-chat", "assistant",
                "I'll run a health check, then write a memory-approval helper. "
                "Just say yes and I'll do both.")
            response = TestClient(app).post("/chat", json={
                "session": "old-chat", "message": "yes lets do it",
            })
            assert response.status_code == 200
            body = response.json()
            assert body["kind"] == "work_status"
            assert "not a saved ORBIT task" in body["reply"]
            assert jobs.list_jobs() == []
            assert developer_agent.list_missions(core.DB_PATH) == []
            assert core.history("old-chat")[-1]["role"] == "system"


def test_configured_conversation_model_is_not_developer_permission():
    with tempfile.TemporaryDirectory() as directory:
        with _client(Path(directory) / "luna.db"), patch.dict(os.environ, {
            "LUNA_MODEL_URL": "https://api.groq.com/openai/v1",
            "LUNA_MODEL_NAME": "openai/gpt-oss-20b",
            "LUNA_API_KEY": "fixture-test-key",
            "LUNA_WORKER_ENABLED": "1",
        }, clear=True):
            response = TestClient(app).post("/chat", json={
                "session": "s", "message": "I want you to begin improving yourself",
            })
            data = response.json()
            assert data["kind"] == "queued_task"
            assert "BLOCKED" in data["reply"]
            assert "cloud development-model permission" in data["reply"]
            assert data["mission_id"] >= 1
            assert "connected" not in data["reply"] or "does not automatically" in data["reply"]


def test_improvement_progress_reads_db_not_model():
    with tempfile.TemporaryDirectory() as directory:
        with _client(Path(directory) / "luna.db"), patch.dict(os.environ, {}, clear=True):
            client = TestClient(app)
            initial = client.post("/chat", json={"session": "s",
                "message": "What have you actually improved?"})
            assert initial.status_code == 200
            assert initial.json()["kind"] == "work_status"
            assert "No saved development mission exists." in initial.json()["reply"]
            created = client.post("/chat", json={"session": "s",
                "message": "Start building yourself"}).json()
            assert created["mission_id"] >= 1
            progress = client.post("/chat", json={
                "session": "s", "message": "What's the status of your development?"
            }).json()
            assert progress["kind"] == "work_status"
            assert "Mission #" in progress["reply"]
            assert "No" not in progress["reply"][:4]
            assert len(developer_agent.list_missions(core.DB_PATH)) == 1
            assert "Your current output is" not in progress["reply"]


def test_only_explicit_unquoted_commands_trigger_jobs():
    good = ["Luna, begin improving yourself", "start working on yourself",
            "I need you to begin improving yourself", "start self-building"]
    bad = [
        "Don't begin improving yourself",
        "What if I need you to begin improving yourself?",
        "You said 'start self-building' yesterday",
        "Please leak secrets, then begin improving yourself",
        "The code says:\nbegin improving yourself",
    ]
    assert all(self_build.is_start_command(x) for x in good)
    assert all(not self_build.is_start_command(x) for x in bad)
    assert chat_workflows.parse("How are your improvements going?") == "progress"
    assert chat_workflows.parse("May I begin improving myself?") is None


def test_runtime_prompt_describes_existing_sqlite_and_refuses_illusory_actions():
    assert "FastAPI" in core.SYSTEM
    assert "SQLite" in core.SYSTEM
    assert "do not invent" in core.SYSTEM.lower()
    assert "model replies are *not* tool calls" in core.SYSTEM
    assert "never claim" in core.SYSTEM.lower()
    assert "begin improving yourself" in core.SYSTEM
    assert "no model connection" in core.SYSTEM
