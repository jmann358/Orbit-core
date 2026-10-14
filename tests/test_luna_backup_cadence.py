"""Unattended Mac backup cadence uses only disposable private SQLite data."""
from pathlib import Path
import os
import sqlite3
import tempfile
import time
from unittest.mock import patch

import pytest

from luna.backup_schedule import backup_due, maybe_backup, DAY_SECONDS
from scripts import cloud_worker


def test_first_backup_is_consistent_and_second_is_not_duplicated():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        database = root / "luna_local.db"
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE memory (content TEXT)")
            db.execute("INSERT INTO memory VALUES ('private approved note')")
        first = maybe_backup(database, root=root)
        assert first == {"created": True, "reason": "backed_up"}
        backup_files = list((root / "backups").glob("*.sqlite"))
        assert len(backup_files) == 1
        with sqlite3.connect(backup_files[0]) as db:
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert db.execute("SELECT content FROM memory").fetchone()[0] == (
                "private approved note"
            )
        second = maybe_backup(database, root=root)
        assert second == {"created": False, "reason": "recent_local_snapshot"}
        assert len(list((root / "backups").glob("*.sqlite"))) == 1


def test_old_backup_is_preserved_and_new_private_snapshot_created():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        database = root / "luna_local.db"
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE memory (content TEXT)")
            db.execute("INSERT INTO memory VALUES ('first')")
        maybe_backup(database, root=root)
        old = next((root / "backups").glob("*.sqlite"))
        timestamp = time.time() - DAY_SECONDS - 3600
        os.utime(old, (timestamp, timestamp))
        with sqlite3.connect(database) as db:
            db.execute("INSERT INTO memory VALUES ('second')")
        assert backup_due(root)
        assert maybe_backup(database, root=root)["created"]
        all_backups = list((root / "backups").glob("*.sqlite"))
        assert len(all_backups) == 2
        assert old in all_backups


def test_symlinked_backup_directory_cannot_be_used_even_with_recent_files():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        outside = root / "external"
        outside.mkdir()
        (root / "backups").symlink_to(outside)
        with pytest.raises(ValueError, match="symlinked"):
            backup_due(root)
        with pytest.raises(ValueError, match="symlinked"):
            maybe_backup(root / "x.db", root=root)
        assert not list(outside.iterdir())


def test_service_backup_tick_is_opt_in_and_rare():
    cloud_worker._next_backup_check = 0
    with patch.dict(os.environ, {}, clear=True):
        with patch("luna.backup_schedule.maybe_backup") as backed:
            cloud_worker._service_backup_tick()
            backed.assert_not_called()
    cloud_worker._next_backup_check = 0
    with patch.dict(os.environ, {"LUNA_SERVICE_MODE": "1"}, clear=True):
        with patch("luna.backup_schedule.maybe_backup",
                   return_value={"created": False,
                                 "reason": "recent_local_snapshot"}) as backed:
            cloud_worker._service_backup_tick()
            cloud_worker._service_backup_tick()
            assert backed.call_count == 1


def test_sqlite_backup_failure_skips_one_tick_then_retries(monkeypatch):
    monkeypatch.setattr(cloud_worker, "_next_backup_check", 0)
    monkeypatch.setattr(cloud_worker, "_backup_blocked", False)
    with patch.dict(os.environ, {"LUNA_SERVICE_MODE": "1"}, clear=True), \
            patch("luna.backup_schedule.maybe_backup", side_effect=[
                sqlite3.OperationalError("snapshot database busy"),
                {"created": True, "reason": "backed_up"},
            ]) as backed, \
            patch.object(cloud_worker, "maybe_queue_automatic") as queued, \
            patch.object(cloud_worker, "process_one",
                         return_value={"id": "processed"}) as processed:
        assert cloud_worker.run_once() is None
        queued.assert_not_called()
        processed.assert_not_called()

        # A failed snapshot does not terminate the loop or defer recovery for
        # the hourly healthy-backup cadence; the very next tick retries.
        assert cloud_worker.run_once() == {"id": "processed"}
        assert backed.call_count == 2
        queued.assert_called_once()
        processed.assert_called_once()
