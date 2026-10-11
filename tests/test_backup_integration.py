from pathlib import Path
from fastapi.testclient import TestClient
from app import app

ROOT=Path(__file__).resolve().parents[1]

def test_dashboard_exposes_validated_backup_control():
    html=TestClient(app).get("/").text
    assert 'id="control-backup"' in html
    assert 'id="backup-status"' in html
    assert "Creating validated SQLite backup" in html
    assert "restore is owner-plan-only" in html

def test_verified_launch_uses_sqlite_backup_script_not_raw_copy():
    script=(ROOT/"scripts"/"verify_and_launch.sh").read_text(encoding="utf-8")
    assert "python scripts/backup_luna.py --quiet" in script
    assert 'cp -p luna_local.db' not in script
