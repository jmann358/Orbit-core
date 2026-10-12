"""Privacy-minimal worker heartbeat, stale and pause checks."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core, jobs
from luna.worker_heartbeat import beat, status


def test_heartbeat_unknown_then_idle_then_stale(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "heart.sqlite"):
        unknown = status()
        assert unknown["state"] == "unknown"
        assert unknown["stale"] is True
        assert unknown["proof_of_liveness"] is False
        saved = beat("idle")
        observed = datetime.fromisoformat(saved["updated_at"])
        fresh = status(now=observed + timedelta(seconds=5))
        assert fresh["state"] == "idle"
        assert fresh["stale"] is False
        assert fresh["recently_observed"] is True
        assert fresh["proof_of_liveness"] is False
        stale = status(now=observed + timedelta(seconds=31))
        assert stale["stale"] is True
        assert stale["recently_observed"] is False
        assert stale["age_seconds"] >= 31


@pytest.mark.parametrize("state", ["starting", "working", "idle", "paused", "attention"])
def test_only_bounded_metadata_is_saved(tmp_path, state):
    with patch.object(core, "DB_PATH", tmp_path / "heart.sqlite"):
        saved = beat(state)
        output = status(now=datetime.fromisoformat(saved["updated_at"]))
        assert output["worker"] == "jobs"
        assert output["state"] == state
        assert output["proof_of_liveness"] is False
        with core.connect() as db:
            names = [
                entry[1] for entry in db.execute("PRAGMA table_info(worker_heartbeat)")
            ]
        assert names == ["worker", "state", "updated_at"]


def test_stopped_heartbeat_is_immediately_nonresponsive(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "heart.sqlite"):
        recorded = beat("stopped")
        outcome = status(now=datetime.fromisoformat(recorded["updated_at"]))
        assert outcome["stale"] is True
        assert outcome["recently_observed"] is False


def test_corrupt_timestamp_reports_unknown_instead_of_crash(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "heart.sqlite"):
        beat("working")
        with core.connect() as db:
            db.execute("UPDATE worker_heartbeat SET updated_at='invalid'")
        result = status()
        assert result["state"] == "unknown"
        assert result["stale"] is True
        with pytest.raises(ValueError, match="timezone aware"):
            status(now=datetime(2025, 1, 1))
        with pytest.raises(ValueError, match="Invalid stale threshold"):
            status(stale_after_seconds=0)


def test_existing_worker_api_distinguishes_enabled_and_heartbeat(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "heart.sqlite"):
        client = TestClient(app)
        fresh = client.get("/agent/worker")
        assert fresh.status_code == 200
        body = fresh.json()
        assert body["enabled"] is True
        assert body["heartbeat"]["recently_observed"] is False
        beat("paused")
        paused = client.get("/agent/worker").json()
        assert paused["enabled"] is True
        assert paused["heartbeat"]["state"] == "paused"
        assert paused["heartbeat"]["proof_of_liveness"] is False
        assert jobs.configure_worker(False)["enabled"] is False
        result = client.get("/agent/worker").json()
        assert result["enabled"] is False
        assert result["heartbeat"]["state"] == "paused"
        home = client.get("/").text
        assert 'id="focus-worker-observation"' in home
        assert "Worker activity unverified:" in home
        assert "A heartbeat is not proof that work has completed." in home
