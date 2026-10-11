import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from luna import core
from luna import jobs


def test_job_inbox_lifecycle():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "jobs.db"):
            first=jobs.create_job("project_health","Check health")
            second=jobs.create_job("github_status","Check CI")
            assert len(jobs.list_jobs())==2
            assert jobs.cancel_job(second)
            assert not jobs.cancel_job(second)
            claimed=jobs.claim_next()
            assert claimed["id"]==first
            assert claimed["kind"]=="project_health"
            assert jobs.claim_next() is None
            assert jobs.finish_job(first,True,"4/4")
            assert jobs.list_jobs()[-1]["state"]=="completed"
            assert not jobs.finish_job(first,True,"again")


def test_interrupted_job_requires_review():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "jobs.db"):
            job_id=jobs.create_job("development_plan","Plan")
            assert jobs.claim_next()["id"]==job_id
            jobs.recover_interrupted()
            record=jobs.list_jobs()[0]
            assert record["state"]=="attention"
            assert "Interrupted" in record["result"]


def test_jobs_reject_unknown_actions():
    with pytest.raises(ValueError):
        jobs.create_job("run_shell","Nope","rm -rf /")
    with pytest.raises(ValueError):
        jobs.create_job("project_health","")
