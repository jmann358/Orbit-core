"""Durable, bounded local job inbox. No arbitrary command execution."""
import sqlite3
from datetime import datetime, timezone
from luna import core

KINDS = ("project_health", "github_status", "development_plan", "self_improvement", "workshop_draft", "autonomous_draft")
STATES = ("queued", "running", "completed", "attention", "cancelled")

def _now():
    return datetime.now(timezone.utc).isoformat()

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS work_items (
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
        detail TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")

def create_job(kind, title, detail=""):
    if kind not in KINDS:
        raise ValueError("Unsupported job kind")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError("Invalid job title")
    if not isinstance(detail, str) or len(detail) > 1200:
        raise ValueError("Invalid job detail")
    with core.connect() as db:
        _setup(db)
        cur=db.execute("INSERT INTO work_items(kind,title,detail,state,created_at,updated_at) VALUES(?,?,?,'queued',?,?)",
                       (kind,title.strip(),detail,_now(),_now()))
        return cur.lastrowid

def list_jobs(limit=40):
    with core.connect() as db:
        _setup(db)
        rows=db.execute("""SELECT id,kind,title,detail,state,result,created_at,updated_at
                           FROM work_items ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
    return [dict(zip(("id","kind","title","detail","state","result","created_at","updated_at"),r)) for r in rows]

def claim_next():
    """Atomic claim for a single worker; unfinished work remains visible."""
    with core.connect() as db:
        _setup(db)
        row=db.execute("SELECT id,kind,detail FROM work_items WHERE state='queued' ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        updated=db.execute("UPDATE work_items SET state='running',updated_at=? WHERE id=? AND state='queued'",
                           (_now(),row[0]))
        if updated.rowcount!=1:
            return None
        return {"id":row[0],"kind":row[1],"detail":row[2]}

def finish_job(job_id, success, result):
    with core.connect() as db:
        _setup(db)
        cur=db.execute("UPDATE work_items SET state=?,result=?,updated_at=? WHERE id=? AND state='running'",
                       ("completed" if success else "attention",str(result)[:1500],_now(),job_id))
        return cur.rowcount==1

def queue_once(kind, title, detail=""):
    """Atomically avoid duplicate queued/running routine work."""
    if kind not in KINDS:
        raise ValueError("Unsupported job kind")
    with core.connect() as db:
        _setup(db)
        existing = db.execute(
            "SELECT id FROM work_items WHERE kind=? AND state IN ('queued','running') LIMIT 1",
            (kind,)).fetchone()
        if existing:
            return {"id": existing[0], "created": False}
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError("Invalid title")
        cur = db.execute(
            "INSERT INTO work_items(kind,title,detail,state,created_at,updated_at) VALUES(?,?,?,'queued',?,?)",
            (kind,title.strip(),detail[:1200],_now(),_now()))
        return {"id":cur.lastrowid, "created": True}

def cancel_job(job_id):
    with core.connect() as db:
        _setup(db)
        cur=db.execute("UPDATE work_items SET state='cancelled',updated_at=? WHERE id=? AND state='queued'",
                       (_now(),job_id))
        return cur.rowcount==1

def recover_interrupted():
    """Interrupted jobs are flagged for inspection, never blindly repeated."""
    with core.connect() as db:
        _setup(db)
        db.execute("UPDATE work_items SET state='attention',result='Interrupted by server restart',updated_at=? WHERE state='running'",(_now(),))
