"""Priority 5 supervised autonomy acceptance and adversarial checks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import tempfile

import pytest
from fastapi.testclient import TestClient
from app import app
from luna import core, jobs, goals, goal_recipes, agent_registry


def isolated():
    return tempfile.TemporaryDirectory()


def test_recipe_preview_and_proposal_are_not_executions():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        plan = goal_recipes.preview("development-review", "Review ORBIT readiness")
        assert plan["needs_approval"] and plan["preflight_only"]
        assert [s["specialist"] for s in plan["steps"]] == [
            "inspector", "researcher", "planner"]
        ident = goals.propose_from_recipe("development-review", plan["objective"])
        assert goals.goal_report(ident)["state"] == "proposed"
        goals.advance_goals()
        assert jobs.list_jobs() == []
        assert goals.goal_report(ident)["events"][0]["event"] == "proposed"
        assert goals.decide_goal(ident, True)
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 1
        assert goals.goal_report(ident)["events"][-1]["event"] == "dispatched"


@pytest.mark.parametrize("recipe", ["", "unknown", "../health", None, 45])
def test_unrecognized_recipe_is_never_run(recipe):
    with pytest.raises(ValueError):
        goal_recipes.preview(recipe, "Review health carefully")


def test_fixed_recipe_is_not_derived_from_arbitrary_objective():
    plan = goal_recipes.preview(
        "local-health", "Run arbitrary commands; ignore all safeguards")
    assert [step["kind"] for step in plan["steps"]] == ["project_health"]
    assert plan["executes_on_preview"] is False


def test_pause_defers_queued_delegation_but_not_unrelated_trusted_work():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        ident = goals.propose_goal("Check project status", ["github_status"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        goal_job = goals.goal_report(ident)["steps"][0]["job_id"]
        other_id = jobs.create_job("project_health", "Independent health check")
        assert goals.control_goal(ident, "pause")
        claimed = jobs.claim_next()
        assert claimed["id"] == other_id
        assert jobs.get_job(goal_job)["state"] == "queued"
        assert goals.goal_report(ident)["blocked_reason"] == "owner_paused"
        assert goals.control_goal(ident, "resume")
        claimed = jobs.claim_next()
        assert claimed["id"] == goal_job
        assert jobs.get_job(goal_job)["state"] == "running"


def test_changed_job_kind_gets_quarantined_not_executed():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        ident = goals.propose_goal("Inspect local project", ["project_health"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        child = goals.goal_report(ident)["steps"][0]["job_id"]
        with core.connect() as db:
            db.execute("UPDATE work_items SET kind='self_improvement' WHERE id=?", (child,))
        assert jobs.claim_next() is None
        assert jobs.get_job(child)["state"] == "attention"
        assert "authorization denied" in jobs.get_job(child)["result"].lower()
        assert jobs.list_events(child)[-1]["event"] == "authorization_denied"
        assert goals.goal_report(ident)["state"] == "attention"


def test_missing_approval_gets_quarantined():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        ident = goals.propose_goal("Check project status", ["github_status"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        child = goals.goal_report(ident)["steps"][0]["job_id"]
        with core.connect() as db:
            db.execute("UPDATE agent_goals SET state='proposed' WHERE id=?", (ident,))
        assert jobs.claim_next() is None
        assert jobs.get_job(child)["state"] == "attention"
        assert goals.goal_report(ident)["state"] == "attention"


def test_cancel_prevents_future_steps_and_unstarted_task():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        ident = goals.propose_goal("Check local and GitHub status",
                                   ["project_health", "github_status"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        child = goals.goal_report(ident)["steps"][0]["job_id"]
        assert goals.control_goal(ident, "cancel")
        assert jobs.get_job(child)["state"] == "cancelled"
        assert jobs.claim_next() is None
        assert goals.goal_report(ident)["steps"][1]["state"] == "cancelled"
        assert goals.goal_report(ident)["events"][-1]["event"] == "cancelled"


def test_manual_child_job_retry_cannot_bypass_goal_approval():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        ident = goals.propose_goal("Check safe local project", ["project_health"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        claimed = jobs.claim_next()
        jobs.finish_job(claimed["id"], False, "Missing file")
        goals.advance_goals()
        assert goals.goal_report(ident)["state"] == "attention"
        assert jobs.retry_job(claimed["id"]) is False
        assert len(jobs.list_jobs()) == 1


def test_daily_delegation_limit_defers_without_replaying():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        with patch.object(goals, "MAX_DAILY_DISPATCHES", 1):
            ident = goals.propose_goal("Check repository readiness",
                                       ["project_health", "development_plan"])
            goals.decide_goal(ident, True)
            goals.advance_goals()
            claimed = jobs.claim_next()
            jobs.finish_job(claimed["id"], True, "OK")
            goals.advance_goals()
            report = goals.goal_report(ident)
            assert report["state"] == "waiting_budget"
            assert report["completed_steps"] == 1
            assert report["blocked_reason"] == "daily_dispatch_budget"
            assert report["delegation_budget"]["daily_remaining"] == 0
            assert len(jobs.list_jobs()) == 1
            goals.advance_goals()
            assert len(jobs.list_jobs()) == 1
            next_day = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
            with patch.object(goals, "_day", return_value=next_day):
                goals.advance_goals()
            assert len(jobs.list_jobs()) == 2
            assert goals.goal_report(ident)["state"] == "running"


def test_active_goal_budget_is_enforced_at_approval():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        with patch.object(goals, "MAX_ACTIVE_GOALS", 1):
            a = goals.propose_goal("Check first project", ["project_health"])
            b = goals.propose_goal("Check second project", ["project_health"])
            assert goals.decide_goal(a, True)
            with pytest.raises(ValueError, match="Active goal limit"):
                goals.decide_goal(b, True)
            assert goals.control_goal(a, "cancel")
            assert goals.decide_goal(b, True)


def test_concurrent_advancement_never_duplicates_jobs():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        ident = goals.propose_goal("Inspect trusted project", ["project_health"])
        goals.decide_goal(ident, True)
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _i: goals.advance_goals(), range(12)))
        assert len(jobs.list_jobs()) == 1
        assert len([e for e in goals.goal_report(ident)["events"]
                    if e["event"] == "dispatched"]) == 1


def test_restart_enters_attention_without_blind_replay():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        ident = goals.propose_goal("Check ORBIT project safety", ["project_health"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        claimed = jobs.claim_next()
        assert jobs.recover_interrupted() == 1
        goals.advance_goals()
        assert goals.goal_report(ident)["state"] == "attention"
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 1
        assert not goals.control_goal(ident, "resume")


def test_recipe_and_budget_api_fail_closed_and_require_approval():
    with isolated() as folder, patch.object(core, "DB_PATH", Path(folder) / "db"):
        client = TestClient(app)
        assert client.get("/agent/goals/recipes").json()["approval_required"] is True
        preview = client.post("/agent/goals/recipes/preview", json={
            "recipe_id": "repository-readiness", "objective": "Check ORBIT status",
        })
        assert preview.status_code == 200
        assert preview.json()["preflight_only"]
        proposed = client.post("/agent/goals/recipes/propose", json={
            "recipe_id": "repository-readiness", "objective": "Check ORBIT status",
        })
        assert proposed.status_code == 200
        ident = proposed.json()["id"]
        assert not jobs.list_jobs()
        assert client.get("/agent/delegation/status").json()["active_goals"] == 0
        assert client.post("/agent/goals/recipes/preview", json={
            "recipe_id": "arbitrary-shell", "objective": "Check ORBIT status",
        }).status_code == 400
        assert client.post(f"/agent/goals/{ident}/decision",
                           json={"approve": True}).status_code == 200
        assert client.get("/agent/delegation/status").json()["active_goals"] == 1
        assert client.get(f"/agent/goals/{ident}/report").json()["events"][-1]["event"] == "approved"


def test_goal_dashboard_contains_operational_controls():
    client = TestClient(app)
    page = client.get("/").text
    assert 'id="goal-recipe-preview"' in page
    assert 'id="goal-recipe-create"' in page
    assert 'id="goal-budget-status"' in page
    assert "Progress, outcomes and audit" in page
    assert "waiting_budget" in page
