import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core,jobs
from luna.activity_timeline import snapshot

def test_timeline_combines_safe_job_and_agent_metadata():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"timeline.db"):
            job_id=jobs.create_job("project_health","Check project health")
            claimed=jobs.claim_next()
            assert claimed["id"]==job_id
            jobs.finish_job(job_id,True,"All good")
            core.record_agent_run("routine_project_checks","passed","Health checks passed")
            data=snapshot()
            kinds={item["kind"] for item in data["events"]}
            assert "job" in kinds
            assert "agent_run" in kinds
            assert data["payloads_excluded"] is True
            assert data["watchdog_included"] is False

def test_timeline_hides_sensitive_labels_and_rejects_bad_limit():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"timeline.db"):
            jobs.create_job("project_health","password=supersecret123")
            data=snapshot()
            assert data["events"][0]["label"]=="Private task"
            try:
                snapshot(0)
                assert False
            except ValueError:
                pass

def test_timeline_api_and_activity_ui():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"timeline.db"):
            client=TestClient(app)
            response=client.get("/control/timeline")
            assert response.status_code==200
            assert response.json()["payloads_excluded"] is True
    html=TestClient(app).get("/").text
    assert 'id="activity-timeline"' in html
    assert "/control/timeline?limit=40" in html
    assert "v1.1.2.3.5.8.13" in html
