from datetime import datetime,timedelta,timezone
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core,jobs,requests,backlog,permissions
from luna.maintenance_audit import audit
from luna.worker_heartbeat import beat

def test_maintenance_audit_detects_stale_metadata_without_payloads():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"audit.db"):
            now=datetime(2026,10,11,20,0,0,tzinfo=timezone.utc)
            beat("jobs","idle")
            job_id=jobs.create_job("project_health","Private task title")
            jobs.claim_next()
            with core.connect() as db:
                db.execute("UPDATE work_items SET updated_at=? WHERE id=?",
                           ((now-timedelta(hours=2)).isoformat(),job_id))
                permissions._setup(db)
                db.execute("""INSERT INTO capability_grants
                  (capability,expires_at,status,approved_by,created_at)
                  VALUES('run_tests',?,'active','owner',?)""",
                  ((now-timedelta(minutes=1)).isoformat(),
                   (now-timedelta(hours=1)).isoformat()))
            task_id=backlog.add_task("Routine health",1,"luna","project_health")
            with core.connect() as db:
                db.execute("UPDATE development_backlog SET state='dispatching' WHERE id=?",(task_id,))
            requests.create_request("decision","high","Owner check required",
                                    "Private request body stays out of audit")
            # Refresh heartbeat at the controlled audit time so it is not the issue under test.
            with core.connect() as db:
                db.execute("""UPDATE worker_heartbeat SET state='idle',current_kind='',
                              updated_at=? WHERE worker='jobs'""",(now.isoformat(),))
            result=audit(now=now)
            codes={item["code"] for item in result["issues"]}
            assert {"stale_running_job","expired_active_grant",
                    "stuck_backlog_dispatch","high_priority_request"} <= codes
            assert result["changes_made"] is False
            assert result["payloads_included"] is False
            assert "Private request body stays out of audit" not in str(result)

def test_maintenance_audit_clear_with_live_worker():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"audit.db"):
            now=datetime.now(timezone.utc)
            written=beat("jobs","idle")
            result=audit(now=datetime.fromisoformat(written["updated_at"]))
            assert result["status"]=="clear"
            assert result["issues"]==[]

def test_maintenance_audit_api_and_dashboard():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"audit.db"):
            beat("jobs","idle")
            with TestClient(app) as client:
                response=client.get("/control/maintenance-audit")
                assert response.status_code==200
                assert response.json()["payloads_included"] is False
    html=TestClient(app).get("/").text
    assert 'id="maintenance-list"' in html
    assert 'id="maintenance-refresh"' in html
    assert "loadMaintenanceAudit()" in html
