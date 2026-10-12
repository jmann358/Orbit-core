"""Check SQLite memory protection and read-only startup probes for Luna."""
import os
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from luna.launch_guard import snapshot_existing_memory
from scripts import start_luna_agent


def _write_memory(db_path):
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, content TEXT)")
        db.execute("INSERT INTO messages(content) VALUES('private approved history')")


def test_private_sqlite_snapshot_preserves_existing_memory_and_integrity():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        original = root / "luna_local.db"
        _write_memory(original)
        backup = snapshot_existing_memory("luna_local.db", project_root=root)
        assert backup is not None and backup.exists()
        assert backup.parent == root / "backups"
        with sqlite3.connect(original) as db:
            assert db.execute("SELECT content FROM messages").fetchone()[0] == (
                "private approved history"
            )
        with sqlite3.connect(backup) as db:
            assert db.execute("SELECT content FROM messages").fetchone()[0] == (
                "private approved history"
            )
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        if os.name != "nt":
            assert backup.stat().st_mode & 0o077 == 0


def test_no_existing_memory_creates_no_database_or_backup():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        assert snapshot_existing_memory(root / "not-created.db",
                                        project_root=root) is None
        assert not (root / "not-created.db").exists()
        assert not (root / "backups").exists()


def test_symlink_memory_rejected_before_snapshot():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        original = root / "actual.db"
        _write_memory(original)
        (root / "linked.db").symlink_to(original)
        with pytest.raises(ValueError, match="symlink"):
            snapshot_existing_memory(root / "linked.db", project_root=root)
        assert not (root / "backups").exists()


def test_corrupted_sqlite_fails_closed_and_removes_bad_backup():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "broken.db").write_text("not a SQLite database")
        with pytest.raises(ValueError, match="backup failed"):
            snapshot_existing_memory("broken.db", project_root=root)
        backups = root / "backups"
        assert not backups.exists() or list(backups.iterdir()) == []


def test_self_build_refuses_start_if_memory_snapshot_fails():
    ready = {
        "python_supported": True, "missing_dependencies": [],
        "developer_model_configured_unverified": False,
        "dashboard_url": "http://127.0.0.1:8000",
        "studio_url": "http://127.0.0.1:8000/agent/studio",
    }
    with patch.dict("os.environ", {}, clear=True):
        with patch.object(start_luna_agent, "check_readiness", return_value=ready):
            with patch.object(start_luna_agent, "discover_ollama",
                              return_value="qwen2.5-coder:7b"):
                with patch("luna.launch_guard.snapshot_existing_memory",
                           side_effect=ValueError("backup failed")):
                    with patch.object(start_luna_agent.subprocess, "Popen") as launch:
                        assert start_luna_agent.main(["--self-build"]) == 2
                        launch.assert_not_called()
