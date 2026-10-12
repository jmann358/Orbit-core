"""Backup verification and copying must not leak SQLite file descriptors."""
from pathlib import Path
import sqlite3

import pytest

from luna import database_backup


def _assert_closed(connections):
    assert connections
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_verify_closes_read_only_connection_on_success(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE truth (answer TEXT)")
        db.execute("INSERT INTO truth VALUES ('retained')")
    real_connect = sqlite3.connect
    opened = []

    def record_connect(*args, **kwargs):
        db = real_connect(*args, **kwargs)
        opened.append(db)
        return db

    monkeypatch.setattr(database_backup.sqlite3, "connect", record_connect)
    result = database_backup.verify(source)
    assert result["integrity_ok"] is True
    _assert_closed(opened)


def test_online_backup_closes_all_connections_and_keeps_wal_rows(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    target = tmp_path / "recovery.db"
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE truth (answer TEXT)")
        db.execute("INSERT INTO truth VALUES ('committed in WAL')")
        db.commit()
    real_connect = sqlite3.connect
    opened = []

    def record_connect(*args, **kwargs):
        db = real_connect(*args, **kwargs)
        opened.append(db)
        return db

    monkeypatch.setattr(database_backup.sqlite3, "connect", record_connect)
    result = database_backup.backup(source, target)
    assert result["verified"] is True
    assert result["source_unchanged"] is True
    assert result["restore_performed"] is False
    assert target.exists()
    assert database_backup.verify(target)["integrity_ok"] is True
    _assert_closed(opened)
    with real_connect(target) as db:
        assert db.execute("SELECT answer FROM truth").fetchone()[0] == "committed in WAL"


def test_verify_closes_connection_when_sqlite_database_is_invalid(tmp_path, monkeypatch):
    source = tmp_path / "corrupted.db"
    source.write_bytes(b"invalid SQLite database bytes")
    real_connect = sqlite3.connect
    opened = []

    def record_connect(*args, **kwargs):
        db = real_connect(*args, **kwargs)
        opened.append(db)
        return db

    monkeypatch.setattr(database_backup.sqlite3, "connect", record_connect)
    with pytest.raises(sqlite3.DatabaseError):
        database_backup.verify(source)
    _assert_closed(opened)
