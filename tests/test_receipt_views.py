"""Readable result pages preserve JSON contracts and escape saved content."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core, goals, jobs


def test_job_result_page_escapes_saved_worker_text_and_keeps_json(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "receipt.sqlite"):
        job_id = jobs.create_job(
            "project_health", "Health <script>alert(1)</script>"
        )
        raw_result = '<img src=x onerror="alert(1)"> & done'
        with core.connect() as db:
            db.execute(
                "UPDATE work_items SET state='completed',result=? WHERE id=?",
                (raw_result, job_id),
            )
        client = TestClient(app)
        view = client.get(f"/agent/jobs/{job_id}/view")
        assert view.status_code == 200
        assert view.headers["cache-control"] == "private, no-store"
        assert "default-src 'none'" in view.headers["content-security-policy"]
        assert view.headers["x-frame-options"] == "DENY"
        assert "text/html" in view.headers["content-type"]
        assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in view.text
        assert "<img src=x onerror=" not in view.text
        assert "<script>alert(1)</script>" not in view.text
        assert "not independently verified" in view.text
        assert f"/agent/jobs/{job_id}/receipt" in view.text
        receipt = client.get(f"/agent/jobs/{job_id}/receipt")
        assert receipt.status_code == 200
        assert receipt.json()["recorded_result"] == raw_result
        assert receipt.json()["result_url"] == f"/agent/jobs/{job_id}/receipt"
        assert receipt.json()["independently_verified"] is False


def test_goal_result_view_shows_real_pending_steps_without_fabricating_work(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "goals.sqlite"):
        objective = "Review <script>unsafe()</script> and run health"
        goal_id = goals.propose_goal(objective, ["project_health"])
        client = TestClient(app)
        page = client.get(f"/agent/goals/{goal_id}/view")
        assert page.status_code == 200
        assert "&lt;script&gt;unsafe()&lt;/script&gt;" in page.text
        assert "<script>unsafe()</script>" not in page.text
        assert "Not queued" in page.text
        assert "Recorded status: <strong>proposed</strong>" in page.text
        assert "independently verified" in page.text
        assert f"/agent/goals/{goal_id}/receipt" in page.text
        assert client.get(f"/agent/goals/{goal_id}/receipt").json()["state"] == "proposed"
        assert client.get(f"/agent/jobs/{goal_id+10000}/view").status_code == 404
        assert client.get(f"/agent/goals/{goal_id+10000}/view").status_code == 404


def test_result_view_is_read_only_and_cannot_create_tasks(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "readonly.sqlite"):
        job_id = jobs.create_job("project_health", "Existing check")
        client = TestClient(app)
        before = client.get("/agent/jobs").json()
        for _ in range(3):
            assert client.get(f"/agent/jobs/{job_id}/view").status_code == 200
        assert client.get("/agent/jobs").json() == before
