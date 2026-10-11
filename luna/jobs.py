"""Durable, bounded local job inbox with audit events and supervised retries.

Only trusted, fixed-kind handlers consume these records. Job titles and details
are never interpreted as Python, shell commands, URLs, or new permissions.
"""
from datetime import datetime, timedelta, timezone
from luna import core

KINDS = ("project_health", "github_status", "development_plan",
         "self_improvement", "workshop_draft")
STATES = ("queued", "running", "retry_wait", "completed", "attention", "cancelled")
MAX_ACTIVE = 50
AUTOMATIC_RETRY_KINDS = frozenset({"github_status"})
MANUAL_RETRY_KINDS = frozenset({
    "project_health", "github_status", "development_plan", "self_improvement"
})
RETRY_AFTER_SECONDS = (30, 120)
FIELDS = ("id", "kind", "title", "detail", "state", "result",
          "created_at", "updated_at", "attempt_count", "max_attempts",
          "next_attempt_at")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _timestamp(now):
    if now is None:
        return _now()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")
    return now.astimezone(timezone.utc).isoformat()


def _attempt_limit(kind):
    return len(RETRY_AFTER_SECONDS) + 1 if kind in AUTOMATIC_RETRY_KINDS else 1


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS work_items (
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
        detail TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    # Existing user databases are migrated in place. No records are deleted.
    columns = {row[1] for row in db.execute("PRAGMA table_info(work_items)")}
    for name, declaration in (
        ("attempt_count", "INTEGER NOT NULL DEFAULT 0"),
        ("max_attempts", "INTEGER NOT NULL DEFAULT 1"),
        ("next_attempt_at", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in columns:
            db.execute("ALTER TABLE work_items ADD COLUMN " + name + " " + declaration)
    db.execute("""CREATE TABLE IF NOT EXISTS work_events (
        id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL, event TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS work_events_job_idx ON work_events(job_id,id)")
    db.execute("""CREATE TABLE IF NOT EXISTS worker_config (
        id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL DEFAULT '')""")
    db.execute("INSERT OR IGNORE INTO worker_config(id,enabled) VALUES(1,1)")


def _event(db, job_id, name, note="", stamp=None):
    db.execute("INSERT INTO work_events(job_id,event,note,created_at) VALUES(?,?,?,?)",
               (job_id, name, str(note)[:400], stamp or _now()))


def _row(row):
    return dict(zip(FIELDS, row))


def _active_count(db):
    return db.execute("SELECT COUNT(*) FROM work_items WHERE state IN "
                      "('queued','running','retry_wait')").fetchone()[0]


def create_job(kind, title, detail=""):
    if kind not in KINDS:
        raise ValueError("Unsupported job kind")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError("Invalid job title")
    if not isinstance(detail, str) or len(detail) > 1200:
        raise ValueError("Invalid job detail")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        if _active_count(db) >= MAX_ACTIVE:
            raise ValueError("Task queue is full; review existing work")
        stamp = _now()
        cursor = db.execute(
            "INSERT INTO work_items(kind,title,detail,state,created_at,updated_at,"
            "max_attempts) VALUES(?,?,?,'queued',?,?,?)",
            (kind, title.strip(), detail, stamp, stamp, _attempt_limit(kind)),
        )
        _event(db, cursor.lastrowid, "queued", "Allowlisted task queued", stamp)
        return cursor.lastrowid


def get_job(job_id):
    with core.connect() as db:
        _setup(db)
        record = db.execute("SELECT " + ",".join(FIELDS) +
                            " FROM work_items WHERE id=?", (job_id,)).fetchone()
    return _row(record) if record else None


def list_jobs(limit=40):
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("Invalid listing limit")
    with core.connect() as db:
        _setup(db)
        rows = db.execute("SELECT " + ",".join(FIELDS) +
                          " FROM work_items ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_row(record) for record in rows]


def list_events(job_id, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid event limit")
    with core.connect() as db:
        _setup(db)
        rows = db.execute(
            "SELECT id,event,note,created_at FROM work_events "
            "WHERE job_id=? ORDER BY id DESC LIMIT ?", (job_id, limit)
        ).fetchall()
    return [{"id":i, "event":e, "note":note, "created_at":at}
            for i,e,note,at in reversed(rows)]


def worker_status():
    with core.connect() as db:
        _setup(db)
        enabled, updated = db.execute(
            "SELECT enabled,updated_at FROM worker_config WHERE id=1"
        ).fetchone()
        work = dict(db.execute(
            "SELECT state,COUNT(*) FROM work_items GROUP BY state"
        ).fetchall())
    return {
        "enabled": bool(enabled), "updated_at": updated,
        "queued": work.get("queued", 0),
        "running": work.get("running", 0),
        "retry_wait": work.get("retry_wait", 0),
        "attention": work.get("attention", 0),
        "pauses_after_current_job": True,
        "scope": "allowlisted, bounded existing local job handlers",
        "auto_apply": False,
        "network_or_permission_expansion": False,
    }


def configure_worker(enabled):
    if type(enabled) is not bool:
        raise ValueError("Enabled must be boolean")
    with core.connect() as db:
        _setup(db)
        db.execute(
            "UPDATE worker_config SET enabled=?,updated_at=? WHERE id=1",
            (int(enabled), _now()),
        )
    return worker_status()


def claim_next(now=None):
    """Atomically claim the first ready task across concurrent SQLite users."""
    stamp = _timestamp(now)
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        if not db.execute("SELECT enabled FROM worker_config WHERE id=1").fetchone()[0]:
            return None
        record = db.execute(
            "SELECT id,kind,detail FROM work_items WHERE state='queued' "
            "OR (state='retry_wait' AND next_attempt_at<=?) "
            "ORDER BY CASE WHEN state='queued' THEN 0 ELSE 1 END,id LIMIT 1",
            (stamp,),
        ).fetchone()
        if record is None:
            return None
        ident,kind,detail = record
        updated = db.execute(
            "UPDATE work_items SET state='running',attempt_count=attempt_count+1,"
            "next_attempt_at='',updated_at=? WHERE id=? AND state IN "
            "('queued','retry_wait')", (stamp, ident),
        )
        if updated.rowcount != 1:
            return None
        _event(db, ident, "claimed", "Worker started attempt", stamp)
        return {"id": ident, "kind": kind, "detail": detail}


def finish_job(job_id, success, result, *, retryable=False, now=None):
    """Only transient, read-only GitHub checks are eligible for bounded retry."""
    if type(success) is not bool or type(retryable) is not bool:
        raise ValueError("Invalid job outcome")
    stamp = _timestamp(now)
    with core.connect() as db:
        _setup(db)
        row = db.execute(
            "SELECT kind,attempt_count,max_attempts FROM work_items "
            "WHERE id=? AND state='running'", (job_id,),
        ).fetchone()
        if row is None:
            return False
        kind,attempt,max_attempts = row
        if success:
            state, next_at, event = "completed", "", "completed"
        elif retryable and kind in AUTOMATIC_RETRY_KINDS and attempt < max_attempts:
            wait = RETRY_AFTER_SECONDS[min(attempt - 1, len(RETRY_AFTER_SECONDS) - 1)]
            next_at = (datetime.fromisoformat(stamp) +
                       timedelta(seconds=wait)).isoformat()
            state, event = "retry_wait", "retry_scheduled"
        else:
            state, next_at, event = "attention", "", "attention"
        cur = db.execute(
            "UPDATE work_items SET state=?,result=?,next_attempt_at=?,updated_at=? "
            "WHERE id=? AND state='running'",
            (state, str(result)[:1500], next_at, stamp, job_id),
        )
        if cur.rowcount:
            _event(db, job_id, event,
                   "Review needed" if state == "attention" else
                   "Transient check will retry" if state == "retry_wait" else
                   "Completed successfully", stamp)
        return cur.rowcount == 1


def queue_once(kind, title, detail=""):
    """Atomically avoid duplicates while an earlier attempt is waiting."""
    if kind not in KINDS:
        raise ValueError("Unsupported job kind")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError("Invalid title")
    if not isinstance(detail, str) or len(detail) > 1200:
        raise ValueError("Invalid detail")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        existing = db.execute(
            "SELECT id FROM work_items WHERE kind=? AND "
            "state IN ('queued','running','retry_wait') LIMIT 1",
            (kind,),
        ).fetchone()
        if existing:
            return {"id": existing[0], "created": False}
        if _active_count(db) >= MAX_ACTIVE:
            raise ValueError("Task queue is full; review existing work")
        stamp = _now()
        cur = db.execute(
            "INSERT INTO work_items(kind,title,detail,state,created_at,"
            "updated_at,max_attempts) VALUES(?,?,?,'queued',?,?,?)",
            (kind, title.strip(), detail, stamp, stamp, _attempt_limit(kind)),
        )
        _event(db, cur.lastrowid, "queued", "Allowlisted routine queued", stamp)
        return {"id": cur.lastrowid, "created": True}


def cancel_job(job_id):
    """Only not-yet-running work can be cancelled."""
    with core.connect() as db:
        _setup(db)
        cur = db.execute(
            "UPDATE work_items SET state='cancelled',next_attempt_at='',"
            "updated_at=? WHERE id=? AND state IN ('queued','retry_wait')",
            (_now(), job_id),
        )
        if cur.rowcount:
            _event(db, job_id, "cancelled", "Owner cancelled pending work")
        return cur.rowcount == 1


def retry_job(job_id):
    """Manual replay requires an explicit API/UI request; no automatic repair."""
    with core.connect() as db:
        _setup(db)
        row = db.execute(
            "SELECT kind FROM work_items WHERE id=? AND state='attention'",
            (job_id,),
        ).fetchone()
        if not row or row[0] not in MANUAL_RETRY_KINDS:
            return False
        if _active_count(db) >= MAX_ACTIVE:
            raise ValueError("Task queue is full; review existing work")
        cur = db.execute(
            "UPDATE work_items SET state='queued',attempt_count=0,"
            "max_attempts=?,next_attempt_at='',result='',updated_at=? "
            "WHERE id=? AND state='attention'",
            (_attempt_limit(row[0]), _now(), job_id),
        )
        if cur.rowcount:
            _event(db, job_id, "manual_retry", "Owner requested a fresh attempt")
        return cur.rowcount == 1


def recover_interrupted():
    """Restart never silently replays an interrupted operation."""
    with core.connect() as db:
        _setup(db)
        ids = [row[0] for row in db.execute(
            "SELECT id FROM work_items WHERE state='running'"
        ).fetchall()]
        stamp = _now()
        for ident in ids:
            changed = db.execute(
                "UPDATE work_items SET state='attention',"
                "result='Interrupted by server restart',updated_at=? "
                "WHERE id=? AND state='running'", (stamp, ident),
            )
            if changed.rowcount:
                _event(db, ident, "interrupted", "Restart requires owner review", stamp)
        return len(ids)
