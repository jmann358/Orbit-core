import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from luna import backlog, core, jobs

def test_opt_in_delegation_and_budget():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder)/"test.db"):
            backlog.add_task("Check local project",1,"luna","project_health")
            backlog.add_task("Write a new feature",1,"human")
            assert backlog.tick()["reason"]=="paused"
            backlog.configure(True,max_jobs=1,max_model_tokens=100)
            first=backlog.tick()
            assert first["queued"]
            assert backlog.tick()["reason"]=="job_budget"
            job=jobs.claim_next()
            assert job["kind"]=="project_health"
            jobs.finish_job(job["id"],True,"OK")
            backlog.reconcile()
            assert backlog.tasks()[0]["state"]=="completed"
            assert backlog.tasks()[1]["state"]=="open"

def test_rejects_untrusted_actions_and_token_limit():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder)/"test.db"):
            with pytest.raises(ValueError):
                backlog.add_task("Deploy app",1,"luna","shell")
            with pytest.raises(ValueError):
                backlog.add_task("Deploy app",1,"human","project_health")
            backlog.add_task("Review project",1,"luna","project_health")
            backlog.configure(True,max_jobs=2,max_model_tokens=50)
            backlog.record_model_tokens(50)
            assert backlog.tick()["reason"]=="token_budget"
            assert not jobs.list_jobs()

def test_disabled_by_default_and_api():
    from fastapi.testclient import TestClient
    from app import app
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"test.db"):
            client=TestClient(app)
            assert client.get("/agent/overnight").json()["enabled"]==0
            assert client.post("/agent/backlog",json={"title":"Unauthorized shell","owner":"luna","kind":"shell"}).status_code==400
            assert client.post("/agent/backlog",json={"title":"Check health","owner":"luna","kind":"project_health"}).status_code==200
            assert len(client.get("/agent/backlog").json()["tasks"])==1


def test_monitoring_jobs_are_safe_delegation_kinds():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"test.db"):
            first=backlog.add_task("Check readiness",1,"luna","readiness_check")
            second=backlog.add_task("Audit maintenance",1,"luna","maintenance_audit")
            items=backlog.tasks()
            kinds={item["kind"] for item in items}
            assert {"readiness_check","maintenance_audit"} <= kinds
            assert first!=second

def test_task_inbox_exposes_monitoring_jobs():
    from fastapi.testclient import TestClient
    from app import app
    html=TestClient(app).get("/").text
    assert '<option value="readiness_check">System readiness</option>' in html
    assert '<option value="maintenance_audit">Maintenance audit</option>' in html
