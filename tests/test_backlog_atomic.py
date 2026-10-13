"""Crash, concurrency and authorization regressions for atomic backlog work."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest

from luna import backlog, core, jobs


def test_dispatch_inserts_job_event_and_source_link_together(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "luna.sqlite"):
        identifier = backlog.add_task("Run real health check", 1, "luna", "project_health")
        backlog.configure(True, max_jobs=1)
        dispatched = backlog.tick()
        assert dispatched["queued"] is True
        assert dispatched["task_id"] == identifier
        row = backlog.tasks()[0]
        assert row["state"] == "queued"
        assert row["job_id"] == dispatched["job_id"]
        assert jobs.get_job(dispatched["job_id"])["kind"] == "project_health"
        events = jobs.list_events(dispatched["job_id"])
        assert [entry["event"] for entry in events] == ["queued"]


def test_failure_after_job_insertion_rolls_back_whole_dispatch(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "luna.sqlite"):
        task_id = backlog.add_task("Run health check safely", 1, "luna", "project_health")
        backlog.configure(True, max_jobs=2)
        original = jobs._create_job_in_transaction

        def interrupt_after_insert(db, kind, title, detail=""):
            original(db, kind, title, detail)
            raise RuntimeError("simulated process interruption before task linking")

        with patch.object(jobs, "_create_job_in_transaction",
                          side_effect=interrupt_after_insert):
            with pytest.raises(RuntimeError, match="simulated process"):
                backlog.tick()
        assert backlog.tasks()[0]["state"] == "open"
        assert backlog.tasks()[0]["job_id"] is None
        assert jobs.list_jobs() == []
        with core.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM work_events").fetchone()[0] == 0
        recovered = backlog.tick()
        assert recovered["queued"] is True
        assert recovered["task_id"] == task_id
        assert len(jobs.list_jobs()) == 1


def test_simultaneous_ticks_never_double_queue_or_exceed_budget(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "luna.sqlite"):
        backlog.add_task("Check task A", 1, "luna", "project_health")
        backlog.add_task("Check task B", 2, "luna", "github_status")
        backlog.configure(True, max_jobs=1)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: backlog.tick(), range(6)))
        assert sum(result["queued"] is True for result in results) == 1
        assert len(jobs.list_jobs()) == 1
        rows = backlog.tasks()
        assert len([row for row in rows if row["state"] == "queued"]) == 1
        assert len([row for row in rows if row["state"] == "open"]) == 1
        assert {r["reason"] for r in results if not r["queued"]} == {"job_budget"}


def test_reject_tampered_unauthorized_backlog_kind(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "luna.sqlite"):
        task_id = backlog.add_task("Review task integrity", 1, "luna", "project_health")
        backlog.configure(True)
        with core.connect() as db:
            db.execute("UPDATE development_backlog SET kind='workshop_draft' WHERE id=?",
                       (task_id,))
        with pytest.raises(ValueError, match="not authorized"):
            backlog.tick()
        assert jobs.list_jobs() == []
        assert backlog.tasks()[0]["state"] == "open"


def test_shared_job_creation_requires_existing_transaction(tmp_path):
    with sqlite3.connect(tmp_path / "direct.sqlite") as db:
        with pytest.raises(ValueError, match="active write transaction"):
            jobs._create_job_in_transaction(db, "project_health", "Test")
