"""ATLAS negative/regression checks for Mac-first candidate (synthetic only).

No real owner database, external provider, service, network or Mac access.
Tests cover exact previously observed boundaries rather than UI slogans.
"""
import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as api
from luna import core
from luna.cloud_worker import connect as cloud_connect, enqueue, claim, finish
from luna.sensitive_intake import screen


@pytest.mark.parametrize("message,category", [
    ("password=private-credential-123", "credential_assignment"),
    ("api_key: topsecret-value", "credential_assignment"),
    ("Bearer ABCDEFGHIJKLMNOP123456", "bearer_token"),
    ("-----BEGIN PRIVATE KEY-----", "private_key"),
    ("123-45-6789", "social_security_number"),
])
def test_sensitive_chat_is_blocked_before_storage_routing_and_model(tmp_path, message, category):
    with patch.object(core, "DB_PATH", tmp_path / "screen.sqlite"), \
         patch.object(api, "respond", side_effect=AssertionError("model called")) as model, \
         patch.object(api, "suggest_from_user_message",
                      side_effect=AssertionError("memory intake called")) as suggest:
        response = TestClient(api.app).post(
            "/chat", json={"session": "privacy", "message": message}
        )
        assert response.status_code == 200
        result = response.json()
        assert result["stored"] is False
        assert result["model_called"] is False
        assert result["kind"] == "notice"
        assert category in result["sensitive_intake"]["categories"]
        assert message not in response.text
        model.assert_not_called()
        suggest.assert_not_called()
        with core.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_sensitivity_results_contain_labels_not_secrets():
    secret = "password=do-not-echo"
    outcome = screen(secret)
    assert outcome["normal_persistence_allowed"] is False
    assert outcome["luna_may_receive"] is False
    assert outcome["broker_operational"] is False
    assert secret not in repr(outcome)
    assert outcome["comprehensive_pii_screening"] is False
    assert screen("Please summarize my safe project status.")["decision"] == "allow"


def test_regular_chat_continues_to_be_persisted(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "ordinary.sqlite"), \
         patch.dict("os.environ", {}, clear=True):
        result = TestClient(api.app).post(
            "/chat", json={"session": "normal", "message": "Hello Luna"}
        )
        assert result.status_code == 200
        assert "stored" not in result.json()
        assert len(core.history("normal")) == 2


@pytest.mark.parametrize("headers", [
    {"Origin": "https://malicious.example"},
    {"Origin": "null"},
    {"Origin": "http://testserver.attacker.example"},
    {"Origin": "http://testserver:8080"},
    {"Referer": "https://malicious.example/page"},
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},
])
def test_local_browser_cross_site_requests_cannot_create_goals(tmp_path, headers):
    with patch.object(core, "DB_PATH", tmp_path / "browser.sqlite"), \
         patch.dict("os.environ", {}, clear=True):
        client = TestClient(api.app)
        denied = client.post("/agent/goals", headers=headers, json={
            "objective": "Inspect local health safely", "steps": ["project_health"]
        })
        assert denied.status_code == 403
        assert client.get("/agent/goals").json() == []


def test_local_host_header_rebinding_rejected_and_loopback_remains_usable(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "host.sqlite"), \
         patch.dict("os.environ", {}, clear=True):
        bad = TestClient(api.app, base_url="http://public.attacker.example")
        assert bad.get("/history").status_code == 403
        local = TestClient(api.app, base_url="http://127.0.0.1:8000")
        assert local.get("/history").status_code == 200
        request = local.post("/agent/goals",
            headers={"Origin": "http://127.0.0.1:8000",
                     "Sec-Fetch-Site": "same-origin"},
            json={"objective": "Local health evidence", "steps": ["project_health"]})
        assert request.status_code == 200
        assert request.json()["state"] == "proposed"


def test_cloud_worker_connections_close_after_commit_and_exception(tmp_path):
    path = tmp_path / "bounded.db"
    with cloud_connect(path) as db:
        db.execute("CREATE TABLE example (v TEXT)")
        db.execute("INSERT INTO example(v) VALUES ('committed')")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")

    with pytest.raises(RuntimeError, match="synthetic rollback"):
        with cloud_connect(path) as rollback:
            rollback.execute("BEGIN IMMEDIATE")
            rollback.execute("INSERT INTO example(v) VALUES ('uncommitted')")
            raise RuntimeError("synthetic rollback")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        rollback.execute("SELECT 1")

    with cloud_connect(path) as checked:
        assert checked.execute("SELECT v FROM example").fetchall() == [("committed",)]


def test_cloud_job_lease_and_finish_still_work_after_connection_changes(tmp_path):
    path = tmp_path / "jobs.db"
    ident = enqueue(path, "heartbeat")
    running = claim(path)
    assert running["id"] == ident
    assert finish(path, ident, running["attempt"], result="ok")


def test_worker_threads_stop_before_test_client_restarts_or_private_db_is_removed():
    # Reproduces the CI temp-directory lifecycle that had an intermittent
    # Directory not empty error when worker threads could outlive TestClient.
    for _ in range(2):
        with TemporaryDirectory() as temporary:
            with patch.object(core, "DB_PATH", Path(temporary) / "luna.sqlite"), \
                 patch.dict("os.environ", {"LUNA_WORKER_ENABLED": "0"}, clear=True):
                with TestClient(api.app) as client:
                    assert client.get("/agent/goals").status_code == 200
                    job_thread = api._job_thread
                    helper_thread = api._custom_agent_thread
                    assert job_thread is not None and job_thread.is_alive()
                    assert helper_thread is not None and helper_thread.is_alive()
                assert not job_thread.is_alive()
                assert not helper_thread.is_alive()
                assert api._job_thread is None
                assert api._custom_agent_thread is None


def test_startup_refuses_to_recover_while_old_worker_is_still_shutting_down():
    class OldWorker:
        def is_alive(self):
            return True

    with patch.object(api, "_job_thread", OldWorker()), \
         patch.object(api._job_stop, "is_set", return_value=True):
        with patch.object(api, "recover_interrupted",
                          side_effect=AssertionError("must not touch DB")):
            with pytest.raises(RuntimeError, match="still shutting down"):
                api._start_job_worker()
