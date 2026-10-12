"""Portable supervised worker with a durable SQLite lease and bounded retries.

The worker performs only explicitly registered safe handlers. It does not
evaluate code, run shell commands, access credentials, or approve proposals.
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALLOWED_KINDS = frozenset(("heartbeat", "project_health"))
MAX_ATTEMPTS = 3
LEASE_SECONDS = 90


def utcnow():
    return datetime.now(timezone.utc)


def connect(path):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
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
        result TEXT NOT NULL DEFAULT ''
    )""")
    return db


def enqueue(path, kind, *, now=None):
    if kind not in ALLOWED_KINDS:
        raise ValueError("Job kind not allowlisted")
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
        db.execute(
            "UPDATE cloud_jobs SET status='queued', lease_until=NULL "
            "WHERE status='running' AND lease_until<=? AND attempts<?",
            (stamp, MAX_ATTEMPTS),
        )
        db.execute(
            "UPDATE cloud_jobs SET status='attention', lease_until=NULL "
            "WHERE status='running' AND lease_until<=? AND attempts>=?",
            (stamp, MAX_ATTEMPTS),
        )
        row = db.execute(
            "SELECT id,kind,attempts FROM cloud_jobs "
            "WHERE status='queued' AND available_at<=? ORDER BY id LIMIT 1",
            (stamp,),
        ).fetchone()
        if row is None:
            return None
        job_id, kind, attempts = row
        db.execute(
            "UPDATE cloud_jobs SET status='running', attempts=attempts+1, "
            "lease_until=?, updated_at=? WHERE id=?",
            (until, stamp, job_id),
        )
        return {"id": job_id, "kind": kind, "attempt": attempts + 1}


def finish(path, job_id, attempt, *, result="", error=None, now=None):
    stamp = (now or utcnow()).isoformat()
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT attempts,status FROM cloud_jobs WHERE id=?", (job_id,),
        ).fetchone()
        if row != (attempt, "running"):
            return False
        if error is None:
            status, delay = "done", stamp
        elif attempt >= MAX_ATTEMPTS:
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
        result = handler()
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
