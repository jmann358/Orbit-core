import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core,jobs,requests
from luna.support_snapshot import build
from luna.worker_heartbeat import beat

def test_support_snapshot_excludes_private_payloads(monkeypatch):
    monkeypatch.setenv("LUNA_MODEL_URL","https://api.openai.com")
    monkeypatch.setenv("LUNA_MODEL_NAME","example-model")
    monkeypatch.setenv("LUNA_API_KEY","super-secret-key-value")
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"support.db"):
            beat("jobs","idle")
            jobs.create_job("project_health","password=private-job-title")
            requests.create_request(
                "decision","high","Review private state",
                "The hidden request body must never be copied.",
                "Hidden request context must never be copied.")
            data=build(Path(__file__).resolve().parents[1])
            text=json.dumps(data)
            assert data["schema"]=="orbit.support.v1"
            assert data["payloads_included"] is False
            assert data["credentials_included"] is False
            assert data["code_included"] is False
            assert data["watchdog_included"] is False
            assert data["vault_included"] is False
            assert "super-secret-key-value" not in text
            assert "private-job-title" not in text
            assert "hidden request body" not in text.lower()
            assert "hidden request context" not in text.lower()

def test_support_snapshot_api_and_copy_button():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"support.db"):
            beat("jobs","idle")
            with TestClient(app) as client:
                response=client.get("/control/support-snapshot")
                assert response.status_code==200
                assert response.json()["schema"]=="orbit.support.v1"
    html=TestClient(app).get("/").text
    assert 'id="control-support"' in html
    assert "/control/support-snapshot" in html
    assert "Safe ORBIT status copied." in html
