"""Codex P1 guardrails for Luna Mac autostart and unattended recovery."""
import os
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from luna.backup_schedule import backup_due, maybe_backup
from scripts import luna_mac_service as mac
from scripts import cloud_worker


def test_custom_database_path_preserved_without_other_environment_secrets():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        original = root / "custom_memory.db"
        with sqlite3.connect(original) as db:
            db.execute("CREATE TABLE memory(text TEXT)")
        with patch.dict(os.environ, {
            "LUNA_DB_PATH": "custom_memory.db",
            "LUNA_API_KEY": "PRIVATE_NEVER_SAVE",
            "LUNA_GITHUB_TOKEN": "PRIVATE_NEVER_SAVE",
        }, clear=True):
            config = mac.plist_config(root=root, home=root)
        env = config["EnvironmentVariables"]
        assert env["LUNA_DB_PATH"] == str(original)
        assert "LUNA_API_KEY" not in env
        assert "LUNA_GITHUB_TOKEN" not in env
        assert "PRIVATE_NEVER_SAVE" not in str(config)


def test_reject_symlinked_custom_database():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        data = root / "real.db"
        with sqlite3.connect(data) as db:
            db.execute("CREATE TABLE memory(text TEXT)")
        linked = root / "linked.db"
        linked.symlink_to(data)
        with patch.dict(os.environ, {"LUNA_DB_PATH": str(linked)}, clear=True):
            with pytest.raises(ValueError, match="symlinked Luna memory"):
                mac.plist_config(root=root, home=root)


def test_untrusted_persistent_launcher_path_is_rejected():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        launcher = root / "scripts" / "start_luna_agent.py"
        launcher.parent.mkdir()
        launcher.write_text("print('mock')\n")
        python = root / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.write_text("mock")
        # Create the untrusted condition explicitly; macOS temp parents are private.
        root.chmod(0o777)
        with pytest.raises(ValueError, match="writable by other users"):
            mac._verify_owner_control(root)
        fake = root / "scripts" / "shortcut.py"
        fake.symlink_to(launcher)
        with pytest.raises(ValueError, match="symlinked source"):
            mac._verify_owner_control(fake)


def test_corrupted_recent_backup_does_not_suppress_fresh_snapshot():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        database = root / "luna.db"
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE memory(note TEXT)")
            db.execute("INSERT INTO memory VALUES ('preserved')")
        directory = root / "backups"
        directory.mkdir()
        corrupt = directory / "luna-before-self-build-broken.sqlite"
        corrupt.write_bytes(b"")
        assert backup_due(root) is True
        assert maybe_backup(database, root=root)["created"] is True
        backups = list(directory.glob("*.sqlite"))
        assert corrupt in backups
        assert len(backups) == 2


def test_backup_failure_prevents_unattended_queue_or_job_processing():
    cloud_worker._next_backup_check = 0
    cloud_worker._backup_blocked = False
    with patch.dict(os.environ, {"LUNA_SERVICE_MODE": "1"}, clear=True):
        with patch("luna.backup_schedule.maybe_backup",
                   side_effect=ValueError("private snapshot failed")) as back:
            with patch.object(cloud_worker, "maybe_queue_automatic") as queued:
                with patch.object(cloud_worker, "process_one") as processed:
                    with patch.object(cloud_worker.time, "monotonic",
                                      return_value=100):
                        assert cloud_worker.run_once() is None
                    with patch.object(cloud_worker.time, "monotonic",
                                      return_value=101):
                        assert cloud_worker.run_once() is None
                    assert back.call_count == 1
                    queued.assert_not_called()
                    processed.assert_not_called()
    assert cloud_worker._backup_blocked is True


def test_worker_recovers_after_next_successful_private_backup():
    cloud_worker._next_backup_check = 0
    cloud_worker._backup_blocked = True
    with patch.dict(os.environ, {"LUNA_SERVICE_MODE": "1"}, clear=True):
        with patch("luna.backup_schedule.maybe_backup",
                   return_value={"created": True, "reason": "backed_up"}):
            with patch.object(cloud_worker, "maybe_queue_automatic"):
                with patch.object(cloud_worker, "process_one",
                                  return_value={"status": "done"}) as process:
                    with patch.object(cloud_worker.time, "monotonic",
                                      return_value=500):
                        assert cloud_worker.run_once() == {"status": "done"}
                    process.assert_called_once()
    assert cloud_worker._backup_blocked is False
