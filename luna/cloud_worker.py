"""Portable supervised worker with a durable SQLite lease and bounded retries.

The worker performs only explicitly registered safe handlers. It does not
evaluate code, run shell commands, access credentials, or approve proposals.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALLOWED_KINDS = frozenset(("heartbeat", "project_health", "development_draft"))
MAX_ATTEMPTS = 3
LEASE_SECONDS = 90


def utcnow():
    return datetime.now(timezone.utc)


@contextmanager
def connect(path):
    """One transaction scope with deterministic closure on every outcome.

    sqlite3.Connection.__exit__ does not close its file descriptor.
    All existing callers use the context-manager API; consent reservations
    must commit once, and failures must roll back.
    """
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        with db:
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("""CREATE TABLE IF NOT EXISTS cloud_jobs (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        available_at TEXT NOT NULL,
        lease_until TEXT,
        result TEXT NOT NULL DEFAULT '',
        payload TEXT NOT NULL DEFAULT ''
    )""")
            columns = {r[1] for r in db.execute("PRAGMA table_info(cloud_jobs)")}
            if "payload" not in columns:
                db.execute("ALTER TABLE cloud_jobs ADD COLUMN payload TEXT NOT NULL DEFAULT ''")
            yield db
    finally:
        db.close()

def enqueue(path, kind, *, now=None, payload=""):
    if kind not in ALLOWED_KINDS:
        raise ValueError("Job kind not allowlisted")
    if kind == "development_draft":
        # Developer jobs are created with their mission atomically by
        # luna.developer_agent.queue_mission, not through this generic API.
        raise ValueError("Use queue_mission for supervised development tasks")
    if payload:
        raise ValueError("Only pre-approved mission IDs may have a payload")
    instant = (now or utcnow()).isoformat()
    with connect(path) as db:
        cursor = db.execute(
            "INSERT INTO cloud_jobs(kind,created_at,updated_at,available_at) VALUES(?,?,?,?)",
            (kind, instant, instant, instant),
        )
        return cursor.lastrowid


def claim(path, *, now=None):
    now = now or utcnow()
    stamp = now.isoformat()
    until = (now + timedelta(seconds=LEASE_SECONDS)).isoformat()
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        # Never silently replay a potentially billable model call after a
        # worker crash or lease expiration.
        db.execute(
            "UPDATE cloud_jobs SET status='attention', lease_until=NULL "
            "WHERE kind='development_draft' AND status='running' "
            "AND lease_until<=?", (stamp,),
        )
        db.execute(
            "UPDATE cloud_jobs SET status='queued', lease_until=NULL "
            "WHERE kind!='development_draft' AND status='running' "
            "AND lease_until<=? AND attempts<?", (stamp, MAX_ATTEMPTS),
        )
        db.execute(
            "UPDATE cloud_jobs SET status='attention', lease_until=NULL "
            "WHERE status='running' AND lease_until<=? AND attempts>=?",
            (stamp, MAX_ATTEMPTS),
        )
        # An owner pause stops new development claims, not existing safe
        # heartbeat or health jobs.
        control_exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='developer_control'"
        ).fetchone()
        paused = bool(db.execute(
            "SELECT paused FROM developer_control WHERE id=1"
        ).fetchone()[0]) if control_exists else False
        # A queued development job must remain untouched if the explicit
        # model opt-in is absent. The rest of Luna's read-only work continues.
        from luna.developer_model import configuration
        development_available = not paused and configuration()["ready"]
        rows = db.execute(
            "SELECT id,kind,attempts,payload FROM cloud_jobs "
            "WHERE status='queued' AND available_at<=? ORDER BY id LIMIT 200",
            (stamp,),
        ).fetchall()
        row = None
        for candidate in rows:
            ident, kind, attempts, payload = candidate
            if kind == "development_draft":
                if paused:
                    continue
                if not development_available:
                    from luna.mission_consent import eligible_in_db
                    if not eligible_in_db(db, payload):
                        continue
            row = candidate
            break
        if row is None:
            return None
        job_id, kind, attempts, payload = row
        db.execute(
            "UPDATE cloud_jobs SET status='running', attempts=attempts+1, "
            "lease_until=?, updated_at=? WHERE id=?",
            (until, stamp, job_id),
        )
        return {"id": job_id, "kind": kind, "attempt": attempts + 1,
                "payload": payload}


def finish(path, job_id, attempt, *, result="", error=None, now=None):
    stamp = (now or utcnow()).isoformat()
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT attempts,status,kind FROM cloud_jobs WHERE id=?", (job_id,),
        ).fetchone()
        if row is None or row[:2] != (attempt, "running"):
            return False
        if error is None:
            status, delay = "done", stamp
        elif attempt >= MAX_ATTEMPTS or row[2] == "development_draft":
            status, delay = "attention", stamp
        else:
            status = "queued"
            delay = ((now or utcnow()) + timedelta(seconds=2 ** attempt)).isoformat()
        db.execute(
            "UPDATE cloud_jobs SET status=?,result=?,updated_at=?,available_at=?,"
            "lease_until=NULL WHERE id=?",
            (status, str(error if error is not None else result)[:300], stamp, delay, job_id),
        )
        return True


def process_one(path, handlers, *, now=None):
    job = claim(path, now=now)
    if job is None:
        return None
    try:
        handler = handlers[job["kind"]]
        result = (handler(job["payload"]) if job["kind"] == "development_draft"
                  else handler())
    except Exception as exc:
        # Never persist exception text, which might contain credentials.
        finish(path, job["id"], job["attempt"], error="Handler failed", now=now)
        return {"id": job["id"], "status": "retry_or_attention"}
    finish(path, job["id"], job["attempt"], result=str(result), now=now)
    return {"id": job["id"], "status": "done"}


def summary(path):
    with connect(path) as db:
        rows = db.execute(
            "SELECT status,COUNT(*) FROM cloud_jobs GROUP BY status"
        ).fetchall()
    return dict(rows)
