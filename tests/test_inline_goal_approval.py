"""Inline goal review uses the real owner decision and fixed-step worker."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core, goals, jobs


def test_home_shows_current_goal_and_inline_scoped_decision_ui(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "ui.sqlite"):
        html = TestClient(app).get("/").text
        assert 'id="focus-active-goal"' in html
        assert 'id="focus-goal-status"' in html
        assert "Approve listed steps" in html
        assert "Reject plan" in html
        assert "Modify plan" in html
        assert "fresh approval required" in html
        assert "'/agent/goals/'+plan.id+'/view'" in html
        assert "Open saved result and audit" in html
        assert "from owner" not in html  # no unverified authority claims


def test_duplicate_approvals_cannot_duplicate_authorized_work(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "race.sqlite"):
        identifier = goals.propose_goal("Check repository safely", ["project_health"])
        def approve(_):
            return TestClient(app).post(
                f"/agent/goals/{identifier}/decision", json=approval_payload(TestClient(app), identifier, True)
            ).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(approve, range(2)))
        assert sorted(statuses) == [200, 409]
        goals.advance_goals()
        goals.advance_goals()
        recorded = goals.goal_report(identifier)
        assert recorded["state"] == "running"
        assert len([s for s in recorded["steps"] if s["job_id"]]) == 1
        assert len(jobs.list_jobs()) == 1
        assert jobs.claim_next()["kind"] == "project_health"


def test_reject_goal_disallows_worker_execution(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "rejected.sqlite"):
        client = TestClient(app)
        identifier = goals.propose_goal("Do not run this check", ["project_health"])
        denied = client.post(f"/agent/goals/{identifier}/decision",
                             json=approval_payload(client, identifier, False))
        assert denied.status_code == 200
        goals.advance_goals()
        assert goals.goal_report(identifier)["state"] == "rejected"
        assert jobs.list_jobs() == []


def approval_payload(client, ident, approve):
    displayed = client.get(f"/agent/goals/{ident}/report").json()
    return {"approve": approve, "expected_revision": displayed["revision"],
            "expected_digest": displayed["plan_digest"]}
