"""SQLite transaction ownership and descriptor lifecycle regressions."""
import sqlite3
from unittest.mock import patch

import pytest

from luna import core, jobs


def test_core_connection_closes_immediately_after_success(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "managed.sqlite"):
        with core.connect() as db:
            db.execute("INSERT INTO messages(session,role,content,created_at) "
                       "VALUES('smoke','user','retained','now')")
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            db.execute("SELECT 1")
        with core.connect() as another:
            text = another.execute(
                "SELECT content FROM messages WHERE session='smoke'"
            ).fetchone()[0]
        assert text == "retained"
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            another.execute("SELECT 1")


def test_core_connection_rolls_back_and_closes_after_exception(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "managed.sqlite"):
        with pytest.raises(RuntimeError, match="interrupt"):
            with core.connect() as db:
                db.execute("INSERT INTO messages(session,role,content,created_at) "
                           "VALUES('smoke','user','uncommitted','now')")
                raise RuntimeError("interrupt before commit")
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            db.execute("SELECT 1")
        with core.connect() as another:
            count = another.execute(
                "SELECT COUNT(*) FROM messages WHERE session='smoke'"
            ).fetchone()[0]
        assert count == 0


def test_begin_immediate_still_works_with_managed_connections(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "managed.sqlite"):
        with core.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO messages(session,role,content,created_at) "
                       "VALUES('job','user','once','now')")
        assert core.history("job") == [{"role": "user", "content": "once"}]
        created = jobs.create_job("project_health", "Check no database locks")
        assert jobs.get_job(created)["state"] == "queued"


def test_repeated_contexts_close_without_gc(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "managed.sqlite"):
        used = []
        for _ in range(40):
            with core.connect() as db:
                db.execute("SELECT 1")
                used.append(db)
        for db in used:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                db.execute("SELECT 1")
