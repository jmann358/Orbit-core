import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import backup,core

def test_backup_api_create_list_and_restore_plan_only():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        db_path=root/"live.db"
        backup_dir=root/"backups"
        with patch.object(core,"DB_PATH",db_path), patch.object(backup,"DEFAULT_BACKUP_DIR",backup_dir):
            core.add_message("s","user","hello")
            client=TestClient(app)

            created=client.post("/control/backups")
            assert created.status_code==200
            data=created.json()
            assert data["integrity"]=="ok"
            assert data["live_database_modified"] is False
            assert data["restore_performed"] is False

            listed=client.get("/control/backups")
            assert listed.status_code==200
            body=listed.json()
            assert len(body["backups"])==1
            assert body["restore_available"] is False
            assert body["restore_mode"]=="owner_plan_only"
            assert body["automatic_delete"] is False

            filename=body["backups"][0]["filename"]
            plan=client.get("/control/backups/"+filename+"/restore-plan")
            assert plan.status_code==200
            pdata=plan.json()
            assert pdata["requires_owner_action"] is True
            assert pdata["restore_performed"] is False
            assert pdata["automatic_overwrite_allowed"] is False

def test_backup_api_rejects_bad_restore_name():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(backup,"DEFAULT_BACKUP_DIR",Path(folder)):
            response=TestClient(app).get("/control/backups/not-a-backup.db/restore-plan")
            assert response.status_code==400
