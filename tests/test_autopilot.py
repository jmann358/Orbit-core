import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from luna import core, autopilot, jobs

def test_autopilot_queues_bounded_jobs_without_repeating():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "test.db"):
            now=datetime(2026,10,11,tzinfo=timezone.utc)
            assert autopilot.status()["enabled"]
            first=autopilot.tick(now)
            assert len(first["queued"])==3
            assert len(jobs.list_jobs())==3
            assert autopilot.tick(now)["queued"]==[]
            assert autopilot.tick(now+timedelta(minutes=31))["queued"]==[]
            autopilot.configure(False)
            assert autopilot.tick(now+timedelta(days=2))["reason"]=="paused"
            assert len(jobs.list_jobs())==3

def test_autopilot_has_no_unsafe_job_kinds():
    assert set(autopilot.ROUTINES) <= {"project_health","development_plan","self_improvement"}
    assert all(kind in jobs.KINDS for kind in autopilot.ROUTINES)
