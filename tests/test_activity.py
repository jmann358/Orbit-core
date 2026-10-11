"""Read-only activity status and recorded job history."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from luna import core, jobs
from app import app


def test_activity_empty_and_recorded_job_transitions():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder)/"activity.db"):
            client=TestClient(app)
            empty=client.get("/control/activity")
            assert empty.status_code==200
            assert empty.json()["status"]=="Idle"
            assert empty.json()["recent"]==[]
            job_id=jobs.create_job("project_health","Check project")
            queued=client.get("/control/activity").json()
            assert queued["status"]=="Queued"
            assert queued["counts"]["queued"]==1
            assert jobs.claim_next()["id"]==job_id
            assert client.get("/control/activity").json()["status"]=="Working"
            jobs.finish_job(job_id,False,"Needs review")
            failed=client.get("/control/activity").json()
            assert failed["status"]=="Needs Attention"
            assert failed["recent"][0]["result"]=="Needs review"
            assert failed["counts"]["attention"]==1


def test_activity_page_contains_all_three_views():
    html=TestClient(app).get("/").text
    assert 'id="activity-nav-status"' in html
    assert 'id="activity-feed"' in html
    assert 'id="activity-history"' in html
    assert 'id="activity-now"' in html
    assert "/control/now" in html
    assert "setInterval(()=>{if(!document.hidden)refreshActivity()},3000)" in html
