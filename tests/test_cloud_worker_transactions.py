"""Observable rollback contract for the shared worker/consent connection."""
import sqlite3

import pytest

from luna.cloud_worker import connect
from luna.developer_agent import queue_mission, TEMPLATES


@pytest.mark.parametrize("explicit_begin", [False, True])
def test_failed_scope_does_not_keep_partial_writes(tmp_path, explicit_begin):
    path = tmp_path / "synthetic.sqlite"
    with connect(path) as db:
        db.execute("CREATE TABLE sample (value TEXT)")
        db.execute("INSERT INTO sample VALUES ('retained')")

    with pytest.raises(RuntimeError, match="interrupted"):
        with connect(path) as db:
            if explicit_begin:
                db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE sample SET value='partial'")
            db.execute("INSERT INTO sample VALUES ('partial')")
            raise RuntimeError("interrupted")

    with connect(path) as db:
        assert db.execute("SELECT value FROM sample").fetchall() == [("retained",)]


def test_successful_scope_commits_all_writes(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with connect(path) as db:
        db.execute("CREATE TABLE sample (value TEXT)")
        db.execute("INSERT INTO sample VALUES ('one')")
        db.execute("INSERT INTO sample VALUES ('two')")
    with sqlite3.connect(path) as reopened:
        assert reopened.execute("SELECT value FROM sample ORDER BY value").fetchall() == [
            ("one",), ("two",)
        ]
    reopened.close()


def test_mission_and_job_remain_atomic_on_enqueue_failure(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with connect(path) as db:
        db.execute("""CREATE TRIGGER reject_job BEFORE INSERT ON cloud_jobs
            BEGIN SELECT RAISE(ABORT, 'synthetic queue failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="synthetic queue failure"):
        queue_mission(path, next(iter(TEMPLATES)))
    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM cloud_jobs").fetchone() == (0,)
        # Setup can itself roll back: either no table or no partial mission.
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='developer_missions'").fetchone()
        if exists:
            assert db.execute("SELECT COUNT(*) FROM developer_missions").fetchone() == (0,)
