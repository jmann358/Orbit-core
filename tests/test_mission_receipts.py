"""A real persisted owner task, worker receipt, and direct result link.

The worker handler is invoked through its existing fixed path; no AI provider,
external services, OS shell, generated code or owner data are touched.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app, _process_job
from luna import core, goals, jobs


def test_chat_to_worker_to_persistent_result_link(tmp_path):
    database = tmp_path / "receipts.sqlite"
    with patch.object(core, "DB_PATH", database):
        client = TestClient(app)
        proposed = client.post("/chat", json={
            "session": "owner", "message": "Luna, begin improving yourself"
        })
        assert proposed.status_code == 200
        data = proposed.json()
        assert data["kind"] == "queued_task"
        job_id = data["job_id"]
        link = data["receipt_url"]
        assert link == f"/agent/jobs/{job_id}/receipt"
        queued = client.get(link).json()
        assert queued["state"] == "queued"
        assert queued["recorded_result"] == ""
        assert queued["worker_reported_complete"] is False

        claimed = jobs.claim_next()
        assert claimed["id"] == job_id
        with patch("luna.development.inspect_source",
                   return_value={"findings": []}), patch(
            "app.project_health",
            return_value={"passed": 3, "total": 3, "checks": []}
        ):
            ok, outcome = _process_job(claimed)
        assert ok is True
        assert outcome == "Health 3/3"
        assert jobs.finish_job(job_id, ok, outcome)

        # Reopen a new API client against the same persisted database.
        reopened = TestClient(app)
        saved = reopened.get(link).json()
        assert saved["receipt_id"] == f"job:{job_id}"
        assert saved["recorded_result"] == "Health 3/3"
        assert saved["state"] == "completed"
        assert saved["worker_reported_complete"] is True
        assert saved["independently_verified"] is False
        assert [e["event"] for e in saved["events"]] == [
            "queued", "claimed", "completed"
        ]
        assert client.get(f"/agent/jobs/{job_id}/events").status_code == 200


def test_goal_receipt_tracks_owner_decision_child_job_and_outcome(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "goals.sqlite"):
        client = TestClient(app)
        goal_id = goals.propose_goal("Check saved goal results", ["project_health"])
        url = f"/agent/goals/{goal_id}/receipt"
        pending = client.get(url).json()
        assert pending["state"] == "proposed"
        assert pending["worker_reported_complete"] is False
        assert pending["steps"][0]["job_id"] is None
        approved = client.post(f"/agent/goals/{goal_id}/decision", json={
            "approve": True
        })
        assert approved.status_code == 200
        goals.advance_goals()
        current = client.get(url).json()
        job_id = current["steps"][0]["job_id"]
        assert job_id is not None
        assert current["steps"][0]["result_url"] == (
            f"/agent/jobs/{job_id}/receipt"
        )
        claimed = jobs.claim_next()
        assert claimed["id"] == job_id
        assert jobs.finish_job(job_id, True, "Checked source files")
        goals.advance_goals()
        finished = client.get(url).json()
        assert finished["state"] == "completed"
        assert finished["worker_reported_complete"] is True
        assert finished["completed_steps"] == 1
        assert finished["total_steps"] == 1
        assert finished["steps"][0]["recorded_result"] == "Checked source files"
        assert finished["events"][-1]["event"] == "completed"
        assert client.get(finished["steps"][0]["result_url"]).json()[
            "recorded_result"] == "Checked source files"


def test_inconsistent_goal_completion_not_reported_as_success(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "corrupt.sqlite"):
        goal_id = goals.propose_goal("Audit fake completion state",
                                     ["project_health"])
        with core.connect() as db:
            db.execute("UPDATE agent_goals SET state='completed' WHERE id=?",
                       (goal_id,))
            db.execute("UPDATE agent_goal_steps SET state='completed' WHERE goal_id=?",
                       (goal_id,))
        result = TestClient(app).get(
            f"/agent/goals/{goal_id}/receipt").json()
        assert result["state"] == "completed"  # stored state is not fabricated
        assert result["inconsistent_completion_state"] is True
        assert result["worker_reported_complete"] is False
        assert result["independently_verified"] is False


def test_missing_receipt_is_404_and_dashboard_links_to_real_results(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "empty.sqlite"):
        client = TestClient(app)
        assert client.get("/agent/jobs/9999/receipt").status_code == 404
        assert client.get("/agent/goals/9999/receipt").status_code == 404
        page = client.get("/").text
        assert "Open saved goal receipt #" in page
        assert "live result and audit trail" in page
