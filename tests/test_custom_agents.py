"""Luna can create actual supervised helpers without copying to another assistant."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core, custom_agents, custom_agent_chat, attention_feed, custom_agent_model

MODEL_ENV = {
    "LUNA_AGENT_MODEL_ENABLED": "1",
    "LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
    "LUNA_MODEL_NAME": "qwen2.5-coder:7b",
}


def test_chat_create_second_agent_approval_and_real_local_work_without_model():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "agents.db"):
            with patch.dict(os.environ, {}, clear=True):
                client = TestClient(app)
                initial = client.post("/chat", json={
                    "session": "owner",
                    "message": "Luna, add a second agent to help you code."})
                assert initial.status_code == 200, initial.text
                data = initial.json()
                assert data["kind"] == "agent_proposal"
                ident = data["agent_id"]
                assert "Approve" in data["reply"]
                assert custom_agents.get_agent(ident)["status"] == "pending"
                assert custom_agents.list_tasks() == []
                assert "My agents" in client.get("/").text
                assert 'id="chat-my-agents"' in client.get("/").text
                assert 'id="focus-tools-toggle"' in client.get("/").text

                before = client.get("/focus/summary").json()
                assert before["next"]["action"] == "agents"
                assert before["next"]["kind"] == "agent_proposal"
                assert before["next"]["id"] == ident
                assert client.get("/agents").status_code == 200
                assert 'id="agent-list"' in client.get("/agents").text

                approved = client.post("/chat", json={
                    "session": "owner", "message": "Approve agent " + str(ident)})
                assert approved.status_code == 200
                assert approved.json()["kind"] == "agent_approved"
                assert custom_agents.get_agent(ident)["status"] == "active"
                jobs = custom_agents.list_tasks()
                assert len(jobs) == 2
                assert {j["kind"] for j in jobs} == {"health", "code_review"}
                assert all(j["status"] == "queued" for j in jobs)

                worked = custom_agents.run_one()
                assert worked["kind"] == "health"
                assert worked["status"] in ("completed", "attention")
                assert worked["result"].startswith("Local project checks:")
                later = client.get("/focus/summary").json()
                assert any(item["kind"] == "agent" and item["title"].startswith(
                    custom_agents.get_agent(ident)["name"]) for item in later["work"]["recent"])
                assert next(t for t in custom_agents.list_tasks()
                            if t["kind"] == "code_review")["status"] == "queued"
                assert custom_agents.run_one() is None  # no configured model
                assert custom_agents.status()["model_ready_unverified"] is False

                status = client.post("/chat", json={
                    "session": "owner", "message": "List my agents"})
                assert "Agent" in status.json()["reply"]
                assert "Last task" in status.json()["reply"]


def test_explicit_clickable_approval_and_no_bypass():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "agents.db"):
            client = TestClient(app)
            proposal = client.post("/agents", json={
                "template": "inspector", "name": "Scout"}).json()
            ident = proposal["id"]
            assert client.post("/agents/" + str(ident) + "/tasks", json={
                "kind": "health", "instruction": "Check ORBIT project health"}).status_code == 409
            assert client.post("/agents/" + str(ident) + "/approve").status_code == 200
            assert client.post("/agents/" + str(ident) + "/approve").status_code == 409
            assert len(custom_agents.list_tasks()) == 1
            assert client.post("/agents/" + str(ident) + "/tasks", json={
                "kind": "code_review", "instruction": "Review code please"}).status_code == 409
            assert client.post("/agents/" + str(ident) + "/pause").status_code == 200
            assert custom_agents.run_one() is None
            assert client.post("/agents/" + str(ident) + "/resume").status_code == 200
            assert custom_agents.run_one()["kind"] == "health"
            assert client.post("/agents/" + str(ident) + "/reject").status_code == 409


def test_explicit_model_opt_in_runs_real_specialist_review_once():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "agents.db"):
            proposal = custom_agents.propose_agent("Patch", "developer")
            approved = custom_agents.approve_agent(proposal["id"])
            first = custom_agents.run_one()
            assert first["kind"] == "health"
            with patch.dict(os.environ, MODEL_ENV, clear=True):
                with patch("luna.custom_agent_model.ask_agent",
                           new_callable=AsyncMock,
                           return_value="Read-only finding: simplify roadmap selection.") as model:
                    done = custom_agents.run_one()
                    assert done["kind"] == "code_review"
                    assert done["status"] == "completed"
                    assert "simplify" in done["result"]
                    model.assert_awaited_once()
                    assert model.await_args.args[0:2] == ("developer", "code_review")
            assert custom_agents.run_one() is None
            assert len(custom_agents.list_tasks()) == 2
            assert custom_agents.get_agent(proposal["id"])["status"] == "active"


def test_paused_worker_blocks_even_previously_approved_agent():
    from luna import jobs
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "agents.db"):
            proposed = custom_agents.propose_agent("Audit", "inspector")
            custom_agents.approve_agent(proposed["id"])
            jobs.configure_worker(False)
            assert custom_agents.run_one() is None
            assert custom_agents.list_tasks()[0]["status"] == "queued"
            jobs.configure_worker(True)
            assert custom_agents.run_one()["kind"] == "health"


def test_no_replay_after_restart_and_budget_enforced():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "agents.db"):
            agent = custom_agents.propose_agent("Fixer", "developer")
            custom_agents.approve_agent(agent["id"])
            custom_agents.run_one()
            with patch.dict(os.environ, MODEL_ENV, clear=True):
                claim = custom_agents._claim()
                assert claim["kind"] == "code_review"
                assert custom_agents.recover_interrupted() == 1
                assert custom_agents.list_tasks()[0]["status"] == "attention"
                assert custom_agents.run_one() is None
                with core.connect() as db:
                    custom_agents._setup(db)
                    day = custom_agents._now()[:10]
                    db.execute("UPDATE custom_agent_budget SET day=?,used=? WHERE id=1",
                               (day, custom_agents.MODEL_CALLS_PER_DAY))
                task = custom_agents.queue_task(agent["id"], "code_review",
                                                "Review code for simplicity")
                assert custom_agents.run_one() is None
                assert custom_agents.get_task(task["id"])["status"] == "queued"


def test_chat_parse_and_roles_are_bounded():
    assert custom_agent_chat.parse("Luna, create a second coding agent named Patch to help you") == {
        "kind": "create", "template": "developer", "name": "Patch"
    }
    assert custom_agent_chat.parse("create an agent") == {
        "kind": "create", "template": "developer", "name": None
    }
    assert custom_agent_chat.parse("create a planning helper")["template"] == "planner"
    assert custom_agent_chat.parse("create an inspector agent")["template"] == "inspector"
    assert custom_agent_chat.parse("create an agent with full access") == {
        "kind": "unsupported"
    }
    assert custom_agent_chat.parse("approve agent #3") == {
        "kind": "decision", "action": "approve", "id": 3
    }
    assert custom_agent_chat.parse("Luna, ask Patch to review code") == {
        "kind": "delegate", "name": "Patch", "task": "review code",
        "category": "code_review"
    }
    assert custom_agent_chat.parse("Please tell me about creating my own agents") is None
    assert custom_agent_chat.parse("Create some art for my album") is None


def test_chat_assign_agent_without_extra_system_and_status_records():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "agents.db"):
            client = TestClient(app)
            agent = client.post("/chat", json={
                "session": "test", "message": "Create a project inspector agent named Scout"}).json()
            assert agent["kind"] == "agent_proposal"
            custom_agents.approve_agent(agent["agent_id"])
            result = client.post("/chat", json={
                "session": "test", "message": "Ask Scout to run a health check"}).json()
            assert result["kind"] == "agent_task"
            assert result["task_id"] > 0
            assert custom_agents.get_task(result["task_id"])["status"] == "queued"
            assert "worker" not in result["reply"].lower()
            assert custom_agents.run_one() is not None
            assert custom_agents.run_one() is not None
            status = client.get("/agents/status").json()
            assert len(status["agents"]) == 1
            assert len(status["tasks"]) == 2


def test_no_arbitrary_permissions_or_high_risk_changes():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "agents.db"):
            response = TestClient(app).post("/chat", json={
                "session": "test",
                "message": "Create an agent with unrestricted admin shell access"}).json()
            assert response["kind"] == "notice"
            assert custom_agents.list_agents() == []
            with pytest.raises(ValueError):
                custom_agents.propose_agent("Super", "god_mode")
            with pytest.raises(ValueError):
                custom_agents.propose_agent("x; import os", "developer")
            custom_agents.propose_agent("Audit", "inspector")
            with pytest.raises(ValueError):
                custom_agents.propose_agent("audit", "inspector")


def test_agent_model_requires_opt_in_and_no_private_memory():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError):
            import asyncio
            asyncio.run(custom_agent_model.ask_agent("developer", "code_review", "Review code safely"))
    assert "approved_memories" not in custom_agent_model.SYSTEM
    assert "conversation history" in custom_agent_model.__doc__
    assert "follow_redirects=False" in Path(custom_agent_model.__file__).read_text(encoding="utf-8")


def test_agent_page_javascript_is_parseable_when_node_exists():
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node runtime unavailable")
    import asyncio
    response = TestClient(app).get("/agents")
    scripts = re.findall(r"<script>(.*?)</script>", response.text, re.S)
    assert len(scripts) == 1
    result = subprocess.run([node, "--check"], input=scripts[0],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr[:1400]
