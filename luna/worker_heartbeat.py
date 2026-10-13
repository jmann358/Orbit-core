"""Durable, privacy-minimal observations of the existing embedded job worker.

Only state and timestamps are stored, never task bodies, credentials, model
output or user content. Recent heartbeat is NOT proof a worker is healthy.
"""
from datetime import datetime, timezone

from luna import core

STATES = frozenset({"starting", "idle", "working", "paused", "attention", "stopped"})
WORKER = "jobs"


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS worker_heartbeat (
        worker TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")


def beat(state):
    """Record an actual worker execution state, not a predicted status."""
    if state not in STATES:
        raise ValueError("Unsupported worker heartbeat state")
    stamp = datetime.now(timezone.utc).isoformat()
    with core.connect() as db:
        _setup(db)
        db.execute(
            "INSERT INTO worker_heartbeat(worker,state,updated_at) "
            "VALUES(?,?,?) ON CONFLICT(worker) DO UPDATE SET "
            "state=excluded.state, updated_at=excluded.updated_at",
            (WORKER, state, stamp),
        )
    return {"worker": WORKER, "state": state, "updated_at": stamp}


def status(*, stale_after_seconds=30, now=None):
    """Give timestamp-based evidence, not a guarantee the process is alive."""
    if type(stale_after_seconds) is not int or not 10 <= stale_after_seconds <= 300:
        raise ValueError("Invalid stale threshold")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Worker heartbeat comparison must be timezone aware")
    instant = instant.astimezone(timezone.utc)
    with core.connect() as db:
        _setup(db)
        row = db.execute(
            "SELECT state,updated_at FROM worker_heartbeat WHERE worker=?",
            (WORKER,),
        ).fetchone()
    if row is None:
        return {
            "worker": WORKER, "state": "unknown", "updated_at": None,
            "age_seconds": None, "stale": True,
            "recently_observed": False, "proof_of_liveness": False,
        }
    try:
        recorded = datetime.fromisoformat(row[1])
        if recorded.tzinfo is None:
            raise ValueError("Untrusted naive timestamp")
        raw_age = (instant - recorded.astimezone(timezone.utc)).total_seconds()
        # A clock correction or corrupted future timestamp must not make a
        # stopped worker appear recently observed for minutes or hours.
        # Allow a small wall-clock adjustment without fabricating long uptime.
        if raw_age < -5:
            raise ValueError("Heartbeat timestamp is implausibly in the future")
        age = max(0.0, raw_age)
    except (ValueError, TypeError, OverflowError):
        return {
            "worker": WORKER, "state": "unknown", "updated_at": None,
            "age_seconds": None, "stale": True,
            "recently_observed": False, "proof_of_liveness": False,
        }
    stale = age > stale_after_seconds or row[0] == "stopped" or row[0] not in STATES
    return {
        "worker": WORKER, "state": row[0] if row[0] in STATES else "unknown",
        "updated_at": row[1], "age_seconds": round(age, 2),
        "stale": stale, "recently_observed": not stale,
        "proof_of_liveness": False,
    }
