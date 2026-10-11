"""Priority 5: approval-gated goal delegation and auditable progress."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import app
from luna import core, goals, jobs


def sandbox():
    return tempfile.TemporaryDirectory()


def test_approved_goal_dispatches_one_step_and_records_audit():
    with sandbox() as tmp, patch.object(core, "DB_PATH", Path(tmp) / "db.sqlite"):
        ident = goals.propose_goal("Check safe project state",
                                   ["project_health", "development_plan"])
        assert goals.advance_goals() is None
        assert not jobs.list_jobs()
        assert goals.decide_goal(ident, True)
        goals.advance_goals()
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 1
        report = goals.goal_report(ident)
        assert report["completed_steps"] == 0
        assert report["total_steps"] == 2
        assert report["next_step"] == 1
        assert report["steps"][0]["job"]["state"] == "queued"
        assert jobs.list_events(report["steps"][0]["job_id"])[0]["event"] == "queued"
        claimed = jobs.claim_next()
        jobs.finish_job(claimed["id"], True, "Health passed")
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 2
        second = jobs.claim_next()
        jobs.finish_job(second["id"], True, "Plan prepared")
        goals.advance_goals()
        assert goals.goal_report(ident)["state"] == "completed"
        assert goals.goal_report(ident)["completed_steps"] == 2


def test_owner_pause_resume_blocks_future_steps():
    with sandbox() as tmp, patch.object(core, "DB_PATH", Path(tmp) / "db.sqlite"):
        ident = goals.propose_goal("Review project health",
                                   ["project_health", "development_plan"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        # A claimed operation may finish, but a paused goal cannot start
        # another queued task or dispatch the next step.
        first = jobs.claim_next()
        assert goals.control_goal(ident, "pause")
        assert not goals.control_goal(ident, "pause")
        jobs.finish_job(first["id"], True, "Completed")
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 1
        assert goals.goal_report(ident)["state"] == "paused"
        assert goals.control_goal(ident, "resume")
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 2
        assert goals.goal_report(ident)["completed_steps"] == 1


def test_owner_cancel_prevents_unstarted_work_and_audits():
    with sandbox() as tmp, patch.object(core, "DB_PATH", Path(tmp) / "db.sqlite"):
        ident = goals.propose_goal("Check repository status",
                                   ["github_status", "project_health"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        first_id = goals.goal_report(ident)["steps"][0]["job_id"]
        assert goals.control_goal(ident, "cancel")
        assert not goals.control_goal(ident, "resume")
        assert goals.goal_report(ident)["state"] == "cancelled"
        assert jobs.get_job(first_id)["state"] == "cancelled"
        assert jobs.list_events(first_id)[-1]["event"] == "cancelled"
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 1


def test_cancel_does_not_kill_in_flight_job():
    with sandbox() as tmp, patch.object(core, "DB_PATH", Path(tmp) / "db.sqlite"):
        ident = goals.propose_goal("Check safe local project", ["project_health"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        claimed = jobs.claim_next()
        assert goals.control_goal(ident, "cancel")
        assert jobs.get_job(claimed["id"])["state"] == "running"
        assert jobs.finish_job(claimed["id"], True, "Finished")
        assert goals.goal_report(ident)["state"] == "cancelled"


def test_worker_pause_blocks_goal_dispatch():
    with sandbox() as tmp, patch.object(core, "DB_PATH", Path(tmp) / "db.sqlite"):
        ident = goals.propose_goal("Inspect project health", ["project_health"])
        goals.decide_goal(ident, True)
        jobs.configure_worker(False)
        goals.advance_goals()
        assert jobs.list_jobs() == []
        jobs.configure_worker(True)
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 1


def test_attention_goal_requires_new_review_not_automatic_replay():
    with sandbox() as tmp, patch.object(core, "DB_PATH", Path(tmp) / "db.sqlite"):
        ident = goals.propose_goal("Review current project",
                                   ["project_health", "development_plan"])
        goals.decide_goal(ident, True)
        goals.advance_goals()
        claimed = jobs.claim_next()
        jobs.finish_job(claimed["id"], False, "Failed")
        goals.advance_goals()
        assert goals.goal_report(ident)["state"] == "attention"
        assert goals.goal_report(ident)["requires_attention"]
        goals.advance_goals()
        assert len(jobs.list_jobs()) == 1
        assert not goals.control_goal(ident, "resume")


def test_goal_api_reports_and_owner_controls():
    with sandbox() as tmp, patch.object(core, "DB_PATH", Path(tmp) / "db.sqlite"):
        client = TestClient(app)
        response = client.post("/agent/goals", json={
            "objective": "Review the project health",
            "steps": ["project_health", "github_status"],
        })
        assert response.status_code == 200
        ident = response.json()["id"]
        assert client.get(f"/agent/goals/{ident}/report").json()["total_steps"] == 2
        assert client.post(f"/agent/goals/{ident}/control",
                           json={"action": "pause"}).status_code == 409
        assert client.post(f"/agent/goals/{ident}/decision",
                           json={"approve": True}).status_code == 200
        assert client.post(f"/agent/goals/{ident}/control",
                           json={"action": "pause"}).json()["state"] == "paused"
        assert client.post(f"/agent/goals/{ident}/control",
                           json={"action": "resume"}).json()["state"] == "approved"
        assert client.post(f"/agent/goals/{ident}/control",
                           json={"action": "invalid"}).status_code == 400
        assert client.get("/agent/goals/999999/report").status_code == 404
