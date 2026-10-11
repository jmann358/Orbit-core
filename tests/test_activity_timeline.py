import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app,VERSION
from luna import core,jobs,bridge,goals,requests
from luna.worker_heartbeat import beat
from luna.activity_timeline import snapshot,current

def test_timeline_combines_safe_job_and_agent_metadata():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"timeline.db"):
            beat("jobs","idle")
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
            beat("jobs","idle")
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
            beat("jobs","idle")
            client=TestClient(app)
            response=client.get("/control/timeline")
            assert response.status_code==200
            assert response.json()["payloads_excluded"] is True
    html=TestClient(app).get("/").text
    assert 'id="activity-timeline"' in html
    assert "/control/timeline?limit=40" in html
    assert "v"+VERSION in html


def test_timeline_includes_goal_bridge_and_owner_request_metadata_only():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"timeline.db"):
            beat("jobs","idle")
            goals.propose_goal("Improve local continuity visibility",["project_health"])
            bridge.create_thread("Review continuity progress","medium","Private bridge body must stay hidden")
            requests.create_request(
                "decision","high","Review local runner status",
                "Private request body must stay hidden","Private context must stay hidden")
            data=snapshot()
            kinds={item["kind"] for item in data["events"]}
            assert {"goal","bridge","owner_request"} <= kinds
            serialized=str(data)
            assert "Private bridge body must stay hidden" not in serialized
            assert "Private request body must stay hidden" not in serialized
            assert "Private context must stay hidden" not in serialized
            assert data["status"]=="Needs Attention"

def test_current_status_prefers_attention_then_active_then_recent():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"timeline.db"):
            beat("jobs","idle")
            requests.create_request(
                "decision","high","Owner decision required",
                "Review this safe decision request.")
            now=current()
            assert now["status"]=="Needs Attention"
            assert now["headline"].startswith("Needs attention:")
            assert now["focus"]["kind"]=="owner_request"
            assert now["payloads_excluded"] is True

def test_current_status_api():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"timeline.db"):
            beat("jobs","idle")
            client=TestClient(app)
            response=client.get("/control/now")
            assert response.status_code==200
            assert response.json()["headline"].startswith("Luna is idle")
