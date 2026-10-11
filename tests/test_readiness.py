import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app,VERSION
from luna import core,readiness

IMAGE="sha256:"+"a"*64

def _safe_dependencies(monkeypatch):
    monkeypatch.setattr(readiness,"inspect_runner",lambda:{
        "runtime":"podman","runtime_available":True})
    monkeypatch.setattr(readiness,"approved_image",lambda:IMAGE)
    monkeypatch.setattr(readiness,"check",lambda capability:True)
    monkeypatch.setattr(readiness,"continuity_status",lambda:{
        "pending":1,"approved":2})
    monkeypatch.setattr(readiness,"autopilot_status",lambda:{
        "enabled":True,"scope":"predefined low-risk local jobs only"})
    monkeypatch.setattr(readiness,"worker_status",lambda:{
        "worker":"jobs","state":"idle","current_kind":"",
        "updated_at":"2026-10-11T20:00:00+00:00","age_seconds":0.0,
        "alive":True,"stale":False})

def test_readiness_reports_capabilities_without_secrets(monkeypatch):
    _safe_dependencies(monkeypatch)
    monkeypatch.setenv("LUNA_MODEL_URL","http://127.0.0.1:11434")
    monkeypatch.setenv("LUNA_MODEL_NAME","local-model")
    monkeypatch.setenv("LUNA_API_KEY","do-not-return-this")
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"readiness.db"):
            result=readiness.snapshot(Path(__file__).resolve().parents[1])
    assert result["ready_for_local_chat"] is True
    assert result["ready_for_isolated_tests"] is True
    assert result["runner"]["runtime"]=="podman"
    assert result["model"]["kind"]=="local"
    assert result["model"]["credential_present"] is False
    assert result["secrets_returned"] is False
    assert "do-not-return-this" not in json.dumps(result)

def test_readiness_api_and_dashboard(monkeypatch):
    _safe_dependencies(monkeypatch)
    monkeypatch.delenv("LUNA_MODEL_URL",raising=False)
    monkeypatch.delenv("LUNA_MODEL_NAME",raising=False)
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"readiness.db"):
            client=TestClient(app)
            response=client.get("/control/readiness")
            assert response.status_code==200
            assert response.json()["checks"]["container_runtime"] is True
    html=TestClient(app).get("/").text
    assert 'id="readiness-list"' in html
    assert 'id="readiness-refresh"' in html
    assert "loadReadiness()" in html
    assert "v"+VERSION in html


def test_readiness_blocks_untrusted_model_endpoint_without_exposing_key(monkeypatch):
    _safe_dependencies(monkeypatch)
    monkeypatch.setenv("LUNA_MODEL_URL","https://example.com/v1")
    monkeypatch.setenv("LUNA_MODEL_NAME","some-model")
    monkeypatch.setenv("LUNA_API_KEY","secret-key-value")
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"readiness.db"):
            result=readiness.snapshot(Path(__file__).resolve().parents[1])
    assert result["model"]["kind"]=="blocked"
    assert result["model"]["trusted_endpoint"] is False
    assert result["model"]["usable"] is False
    assert result["ready_for_model_chat"] is False
    assert "secret-key-value" not in json.dumps(result)

def test_readiness_cloud_requires_credential(monkeypatch):
    _safe_dependencies(monkeypatch)
    monkeypatch.setenv("LUNA_MODEL_URL","https://api.openai.com/v1")
    monkeypatch.setenv("LUNA_MODEL_NAME","approved-model")
    monkeypatch.delenv("LUNA_API_KEY",raising=False)
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"readiness.db"):
            result=readiness.snapshot(Path(__file__).resolve().parents[1])
    assert result["model"]["kind"]=="cloud"
    assert result["model"]["trusted_endpoint"] is True
    assert result["model"]["usable"] is False
    assert result["model"]["reason"]=="cloud_credential_missing"
