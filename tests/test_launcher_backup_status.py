"""Startup does not claim it created a backup when it skipped the copy."""
from unittest.mock import patch

import pytest

from scripts import start_luna_agent


@pytest.fixture(autouse=True)
def offline_port_probe(monkeypatch):
    # Backup-message tests use synthetic launch conditions, not host sockets.
    monkeypatch.setattr(start_luna_agent, "dashboard_port_occupied", lambda: False)


@pytest.mark.parametrize("backup,expected,forbidden", [
    ({"created": False, "reason": "recent_local_snapshot"},
     "recent verified private SQLite backup already exists",
     "Created a private SQLite safety snapshot"),
    ({"created": False, "reason": "new_database"},
     "No existing SQLite database was available to back up",
     "Created a private SQLite safety snapshot"),
    ({"created": True, "reason": "backed_up"},
     "Created a private SQLite safety snapshot before self-building",
     "no new snapshot was created"),
])
def test_self_build_backup_claims_are_factual(
        capsys, monkeypatch, backup, expected, forbidden):
    monkeypatch.setenv("LUNA_SERVICE_MODE", "1")
    monkeypatch.delenv("LUNA_CLOUD_MODE", raising=False)
    with patch.object(start_luna_agent, "check_readiness", return_value={
            "python_supported": True, "missing_dependencies": [],
            "developer_model_configured_unverified": False,
            "dashboard_url": "http://127.0.0.1:8000",
            "studio_url": "http://127.0.0.1:8000/agent/studio",
        }), patch.object(start_luna_agent, "discover_ollama",
                         return_value="local-coder"), patch(
            "luna.backup_schedule.maybe_backup", return_value=backup) as copied, patch(
            "subprocess.Popen", side_effect=KeyboardInterrupt):
        assert start_luna_agent.main(["--self-build"]) == 130
    text = capsys.readouterr().out
    assert expected in text
    assert forbidden not in text
    copied.assert_called_once()
