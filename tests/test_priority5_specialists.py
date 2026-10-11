"""Capability registry must remain bounded and non-executing."""
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app import app
from luna import core, goals, agent_registry


def test_specialist_registry_is_explicit_and_immutable():
    agents = agent_registry.list_agents()
    assert {a["id"] for a in agents} == {"inspector", "researcher", "planner"}
    assert all(not a["can_execute_code"] and not a["can_spend"]
               and not a["can_change_permissions"] for a in agents)
    assert agent_registry.specialist_for("project_health") == "inspector"
    assert agent_registry.specialist_for("github_status") == "researcher"
    assert agent_registry.specialist_for("development_plan") == "planner"
    with pytest.raises(TypeError):
        agent_registry.AGENTS["intruder"] = {}
    agents[0]["capabilities"].append("run_shell")
    assert "run_shell" not in agent_registry.list_agents()[0]["capabilities"]


@pytest.mark.parametrize("kind", ["run_shell", "workshop_draft",
                                    "self_improvement", "", None, 5])
def test_unknown_capabilities_fail_closed(kind):
    with pytest.raises(ValueError):
        agent_registry.specialist_for(kind)


def test_report_identifies_bounded_specialist_per_step():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "db.sqlite"):
            ident = goals.propose_goal("Review repository and project",
                                       ["project_health", "github_status"])
            report = goals.goal_report(ident)
            assert [step["specialist"] for step in report["steps"]] == [
                "inspector", "researcher"]
            assert report["state"] == "proposed"
            assert not report["requires_attention"]


def test_specialist_api_is_read_only_and_does_not_expand_permissions():
    client = TestClient(app)
    response = client.get("/agent/specialists")
    assert response.status_code == 200
    data = response.json()
    assert len(data["specialists"]) == 3
    assert data["model_agents"] is False
    assert data["dynamic_plugins"] is False
    assert all(not x["can_execute_code"] for x in data["specialists"])
