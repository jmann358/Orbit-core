"""Priority 4: durable supervised task execution, bounded retries, audit and pause."""
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from luna import core, jobs
from luna.job_operations import run_once
from luna.requests import list_requests


def new_db():
    directory = tempfile.TemporaryDirectory()
    path = Path(directory.name) / "test.db"
    return directory, path


def test_existing_job_table_migrates_without_data_loss():
    directory, path = new_db()
    try:
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE work_items (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
                detail TEXT NOT NULL, state TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            db.execute("INSERT INTO work_items VALUES "
                       "(1,'project_health','Old task','','running','','old','old')")
        with patch.object(core, "DB_PATH", path):
            assert jobs.recover_interrupted() == 1
            item = jobs.get_job(1)
            assert item["title"] == "Old task"
            assert item["state"] == "attention"
            assert item["attempt_count"] == 0
            assert jobs.recover_interrupted() == 0
            assert [event["event"] for event in jobs.list_events(1)] == ["interrupted"]
    finally:
        directory.cleanup()


def test_persistent_audit_and_successful_lifecycle():
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            ident = jobs.create_job("development_plan", "Plan documentation")
            assert jobs.get_job(ident)["attempt_count"] == 0
            claimed = jobs.claim_next()
            assert claimed["id"] == ident
            assert jobs.get_job(ident)["attempt_count"] == 1
            assert jobs.finish_job(ident, True, "Reviewed")
            assert not jobs.finish_job(ident, True, "Duplicate")
            assert jobs.get_job(ident)["state"] == "completed"
            assert jobs.claim_next() is None
            assert [e["event"] for e in jobs.list_events(ident)] == [
                "queued", "claimed", "completed"
            ]
    finally:
        directory.cleanup()


def test_transient_github_failure_retries_at_most_twice():
    directory, path = new_db()
    base = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    try:
        with patch.object(core, "DB_PATH", path):
            ident = jobs.create_job("github_status", "Check GitHub")
            assert jobs.get_job(ident)["max_attempts"] == 3
            assert jobs.claim_next(now=base)["id"] == ident
            assert jobs.finish_job(ident, False, "GitHub unavailable",
                                   retryable=True, now=base)
            first = jobs.get_job(ident)
            assert first["state"] == "retry_wait"
            assert first["attempt_count"] == 1
            assert jobs.claim_next(now=base + timedelta(seconds=29)) is None
            assert jobs.claim_next(now=base + timedelta(seconds=30))["id"] == ident
            assert jobs.finish_job(ident, False, "GitHub unavailable",
                                   retryable=True, now=base + timedelta(seconds=30))
            assert jobs.claim_next(now=base + timedelta(seconds=149)) is None
            assert jobs.claim_next(now=base + timedelta(seconds=150))["id"] == ident
            assert jobs.finish_job(ident, False, "GitHub unavailable",
                                   retryable=True, now=base + timedelta(seconds=150))
            end = jobs.get_job(ident)
            assert end["state"] == "attention"
            assert end["attempt_count"] == 3
            assert jobs.claim_next(now=base + timedelta(days=1)) is None
            assert [e["event"] for e in jobs.list_events(ident)].count(
                "retry_scheduled") == 2
    finally:
        directory.cleanup()


def test_no_automatic_retry_for_failed_local_or_model_jobs():
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            for kind in ("project_health", "workshop_draft"):
                ident = jobs.create_job(kind, kind + " task")
                assert jobs.claim_next()["id"] == ident
                assert jobs.finish_job(ident, False, "Failed", retryable=True)
                assert jobs.get_job(ident)["state"] == "attention"
                assert jobs.get_job(ident)["max_attempts"] == 1
    finally:
        directory.cleanup()


def test_pause_is_persistent_and_blocks_new_claims():
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            ident = jobs.create_job("project_health", "Check project")
            assert jobs.configure_worker(False)["enabled"] is False
            assert jobs.worker_status()["enabled"] is False
            assert jobs.claim_next() is None
            assert jobs.get_job(ident)["state"] == "queued"
            assert jobs.configure_worker(True)["enabled"]
            assert jobs.claim_next()["id"] == ident
            assert jobs.get_job(ident)["state"] == "running"
            assert jobs.configure_worker(False)["enabled"] is False
            # A running task completes; the pause affects subsequent tasks.
            assert jobs.finish_job(ident, True, "Ready")
    finally:
        directory.cleanup()


def test_manual_retry_requires_attention_and_rejects_model_calls():
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            ident = jobs.create_job("project_health", "Inspect")
            assert not jobs.retry_job(ident)
            assert jobs.claim_next()["id"] == ident
            assert jobs.finish_job(ident, False, "Attention")
            assert jobs.retry_job(ident)
            assert not jobs.retry_job(ident)
            assert jobs.get_job(ident)["attempt_count"] == 0
            assert jobs.claim_next()["id"] == ident
            assert jobs.finish_job(ident, True, "Resolved")
            other = jobs.create_job("workshop_draft", "Prepare draft")
            assert jobs.claim_next()["id"] == other
            assert jobs.finish_job(other, False, "No provider")
            assert not jobs.retry_job(other)
            assert [e["event"] for e in jobs.list_events(ident)].count(
                "manual_retry") == 1
    finally:
        directory.cleanup()


def test_cancel_pending_retry_and_deduplication():
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            ident = jobs.create_job("github_status", "Check CI")
            assert jobs.claim_next()["id"] == ident
            assert jobs.finish_job(ident, False, "GitHub unavailable", retryable=True)
            assert jobs.queue_once("github_status", "Another CI check") == {
                "id": ident, "created": False
            }
            assert jobs.cancel_job(ident)
            assert not jobs.cancel_job(ident)
            assert jobs.get_job(ident)["state"] == "cancelled"
            assert jobs.claim_next() is None
    finally:
        directory.cleanup()


def test_worker_step_escalates_only_after_exhausting_safe_retries():
    directory, path = new_db()
    base = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    try:
        with patch.object(core, "DB_PATH", path):
            jobs.create_job("github_status", "Check remote workflow")
            def failed(_job):
                return False, "GitHub unavailable"
            first = run_once(failed, now=base)
            assert first["state"] == "retry_wait"
            assert run_once(failed, now=base + timedelta(seconds=10)) is None
            second = run_once(failed, now=base + timedelta(seconds=30))
            assert second["state"] == "retry_wait"
            final = run_once(failed, now=base + timedelta(seconds=150))
            assert final["state"] == "attention"
            issue = list_requests(open_only=True)
            assert len(issue) == 1
            assert issue[0]["title"] == "GitHub check retry limit reached"
            assert run_once(failed, now=base + timedelta(days=1)) is None
    finally:
        directory.cleanup()


def test_handler_exception_fails_closed_without_unbounded_replay():
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            jobs.create_job("project_health", "Health check")
            def broken(_job):
                raise RuntimeError("Oops")
            finished = run_once(broken)
            assert finished["state"] == "attention"
            assert "Task failed" in finished["result"]
            assert run_once(broken) is None
    finally:
        directory.cleanup()


def test_worker_routes_show_audit_and_gate_manual_retry():
    from app import app
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            client = TestClient(app)
            assert client.get("/agent/worker").json()["enabled"] is True
            assert client.post("/agent/worker", json={"enabled": False}).status_code == 200
            created = client.post("/agent/jobs", json={
                "kind": "project_health", "title": "Inspect locally",
            }).json()
            ident = created["id"]
            assert jobs.claim_next() is None
            assert client.post("/agent/worker", json={"enabled": True}).status_code == 200
            assert jobs.claim_next()["id"] == ident
            assert jobs.finish_job(ident, False, "Check failed")
            events = client.get("/agent/jobs/" + str(ident) + "/events")
            assert events.status_code == 200
            assert len(events.json()["events"]) >= 3
            assert client.post("/agent/jobs/" + str(ident) + "/retry").status_code == 200
            assert jobs.get_job(ident)["state"] == "queued"
            assert client.post("/agent/jobs/" + str(ident) + "/retry").status_code == 409
            assert client.get("/agent/jobs/999999/events").status_code == 404
    finally:
        directory.cleanup()


def test_queue_limit_fails_closed():
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            for number in range(jobs.MAX_ACTIVE):
                jobs.create_job("project_health", "Health " + str(number))
            with pytest.raises(ValueError, match="full"):
                jobs.create_job("development_plan", "Another task")
            assert len(jobs.list_jobs(limit=jobs.MAX_ACTIVE)) == jobs.MAX_ACTIVE
    finally:
        directory.cleanup()


def test_autopilot_routines_are_audited_and_not_duplicated_during_retry_wait():
    from luna import autopilot
    directory, path = new_db()
    try:
        with patch.object(core, "DB_PATH", path):
            current = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc)
            created = autopilot.tick(now=current)["queued"]
            assert len(created) == 3
            original = next(x for x in created if x["kind"] == "project_health")
            assert jobs.list_events(original["job_id"])[0]["event"] == "queued"
            with core.connect() as db:
                db.execute(
                    "UPDATE work_items SET state='retry_wait',next_attempt_at=? "
                    "WHERE id=?", ((current + timedelta(hours=1)).isoformat(),
                                    original["job_id"])
                )
            assert autopilot.tick(now=current+timedelta(minutes=31))["queued"] == []
            assert len(jobs.list_jobs()) == 3
    finally:
        directory.cleanup()


def test_worker_dashboard_controls_are_visible():
    from app import home
    html = home()
    assert 'id="worker-toggle"' in html
    assert 'id="worker-status"' in html
    assert "View activity history" in html
    assert "Retry with my approval" in html
    assert "/agent/worker" in html
