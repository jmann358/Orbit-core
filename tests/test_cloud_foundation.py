"""Cloud-hosting security and durable background-worker contract tests."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import app
from luna.cloud_security import cloud_mode, valid_configuration, owner_token_valid
from luna.cloud_worker import enqueue, claim, finish, process_one, summary, MAX_ATTEMPTS

ROOT = Path(__file__).resolve().parents[1]


def _settings():
    return {
        "LUNA_CLOUD_MODE": "1",
        "LUNA_OWNER_TOKEN": "S" * 40,
        "LUNA_PUBLIC_ORIGIN": "https://luna.example.com",
    }


def test_cloud_mode_disabled_by_default():
    assert cloud_mode({}) is False
    with patch.dict("os.environ", {}, clear=True):
        response = TestClient(app).get("/")
    assert response.status_code == 200


def test_cloud_mode_fails_closed_without_configuration():
    with patch.dict("os.environ", {"LUNA_CLOUD_MODE": "1"}, clear=True):
        response = TestClient(app).get("/")
    assert response.status_code == 503


def test_owner_token_required_on_every_route_and_not_exposed():
    settings = _settings()
    with patch.dict("os.environ", settings, clear=True):
        client = TestClient(app, base_url="https://luna.example.com")
        assert client.get("/").status_code == 401
        assert client.get("/history").status_code == 401
        assert client.get("/sessions").status_code == 401
        assert client.post("/chat", json={"message": "Hello"}).status_code == 401
        ok = client.get("/", headers={"Authorization": "Bearer " + settings["LUNA_OWNER_TOKEN"]})
        assert ok.status_code == 200
        assert "no-store" == ok.headers["cache-control"]
        assert settings["LUNA_OWNER_TOKEN"] not in ok.text


def test_insecure_scheme_and_cross_site_write_are_rejected():
    settings = _settings()
    token = {"Authorization": "Bearer " + settings["LUNA_OWNER_TOKEN"]}
    with patch.dict("os.environ", settings, clear=True):
        assert TestClient(app, base_url="http://luna.example.com").get(
            "/", headers=token,
        ).status_code == 403
        client = TestClient(app, base_url="https://luna.example.com")
        assert client.post("/chat", headers={**token, "Origin": "https://evil.example"},
                           json={"message": "Hello"}).status_code == 403


def test_bad_public_origin_and_short_secret_rejected():
    settings = _settings()
    for bad in ("http://luna.example.com", "https://luna.example.com/path",
                "https://user:pass@luna.example.com", "https://luna.example.com:8443"):
        assert not valid_configuration({**settings, "LUNA_PUBLIC_ORIGIN": bad})
    assert not valid_configuration({**settings, "LUNA_OWNER_TOKEN": "short"})
    assert not owner_token_valid("Bearer wrong", settings)


def test_job_allowlist_and_durable_restart():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "jobs.sqlite"
        try:
            enqueue(path, "arbitrary_shell_command")
            assert False, "non-allowlisted job accepted"
        except ValueError:
            pass
        job_id = enqueue(path, "heartbeat")
        job = claim(path)
        assert job["id"] == job_id
        assert job["attempt"] == 1
        assert finish(path, job_id, 1, result="alive")
        assert summary(path) == {"done": 1}
        assert claim(path) is None
        assert not finish(path, job_id, 1, result="stale completion")


def test_worker_lease_expiry_retries_then_requires_attention():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "jobs.sqlite"
        enqueue(path, "heartbeat", now=now)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            job = claim(path, now=now + timedelta(seconds=100 * (attempt - 1)))
            assert job["attempt"] == attempt
        assert claim(path, now=now + timedelta(seconds=100 * MAX_ATTEMPTS)) is None
        assert summary(path)["attention"] == 1


def test_worker_processes_only_registered_safe_handler():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "jobs.sqlite"
        enqueue(path, "heartbeat")
        calls = []
        assert process_one(path, {"heartbeat": lambda: calls.append("ran") or "alive"})["status"] == "done"
        assert calls == ["ran"]
        assert summary(path) == {"done": 1}


def test_worker_failure_is_sanitized_and_retried():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "jobs.sqlite"
        enqueue(path, "heartbeat")
        def failure():
            raise RuntimeError("SECRET-MUST-NOT-LOG")
        result = process_one(path, {"heartbeat": failure})
        assert result["status"] == "retry_or_attention"
        from luna.cloud_worker import connect
        with connect(path) as db:
            text = db.execute("SELECT result FROM cloud_jobs").fetchone()[0]
        assert text == "Handler failed"
        assert summary(path) == {"queued": 1}


def test_cloud_worker_check_does_not_execute_jobs():
    spec = importlib.util.spec_from_file_location("cloud_worker_script", ROOT / "scripts/cloud_worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with patch.object(module, "run_once", side_effect=AssertionError("must not execute")):
        assert module.main(["--check"]) == 0
