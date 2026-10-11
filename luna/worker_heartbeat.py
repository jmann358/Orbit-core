"""Durable metadata-only heartbeat for Luna's local background worker."""
from datetime import datetime, timezone

from luna import core

WORKERS=frozenset({"jobs"})
STATES=frozenset({"starting","idle","working","attention","stopped"})

def _now():
    return datetime.now(timezone.utc).isoformat()

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS worker_heartbeat (
      worker TEXT PRIMARY KEY,
      state TEXT NOT NULL,
      current_kind TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL)""")

def beat(worker,state,current_kind=""):
    if worker not in WORKERS:
        raise ValueError("Unsupported worker")
    if state not in STATES:
        raise ValueError("Unsupported worker state")
    if not isinstance(current_kind,str) or len(current_kind)>64:
        raise ValueError("Invalid work kind")
    if current_kind and not all(ch.isalnum() or ch in "_:-" for ch in current_kind):
        raise ValueError("Work kind must be a bounded metadata token")
    now=_now()
    with core.connect() as db:
        _setup(db)
        db.execute("""INSERT INTO worker_heartbeat(worker,state,current_kind,updated_at)
                      VALUES(?,?,?,?)
                      ON CONFLICT(worker) DO UPDATE SET
                        state=excluded.state,
                        current_kind=excluded.current_kind,
                        updated_at=excluded.updated_at""",
                   (worker,state,current_kind,now))
    return {"worker":worker,"state":state,"current_kind":current_kind,"updated_at":now}

def status(worker="jobs",stale_after_seconds=20,now=None):
    if worker not in WORKERS:
        raise ValueError("Unsupported worker")
    if type(stale_after_seconds) is not int or not 5<=stale_after_seconds<=300:
        raise ValueError("Invalid stale threshold")
    now=now or datetime.now(timezone.utc)
    with core.connect() as db:
        _setup(db)
        row=db.execute(
            "SELECT state,current_kind,updated_at FROM worker_heartbeat WHERE worker=?",
            (worker,)).fetchone()
    if row is None:
        return {"worker":worker,"state":"unknown","current_kind":"",
                "updated_at":None,"alive":False,"stale":True}
    updated=datetime.fromisoformat(row[2])
    age=max(0.0,(now-updated).total_seconds())
    stale=age>stale_after_seconds or row[0]=="stopped"
    return {"worker":worker,"state":row[0],"current_kind":row[1],
            "updated_at":row[2],"age_seconds":round(age,1),
            "alive":not stale,"stale":stale}
