"""Persisted development backlog and bounded opt-in unattended job delegation."""
from datetime import datetime, timezone
from luna import core, jobs

ALLOWED = ("project_health", "github_status", "development_plan", "self_improvement")
OWNERS = ("luna", "assistant", "human")
PRIORITIES = (1, 2, 3)

def _now():
    return datetime.now(timezone.utc).isoformat()

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS development_backlog (
      id INTEGER PRIMARY KEY, title TEXT NOT NULL, priority INTEGER NOT NULL,
      owner TEXT NOT NULL, kind TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT 'open',
      job_id INTEGER, created_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS overnight_settings (
      id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
      max_jobs INTEGER NOT NULL DEFAULT 3, max_model_tokens INTEGER NOT NULL DEFAULT 0,
      used_model_tokens INTEGER NOT NULL DEFAULT 0, session_day TEXT NOT NULL DEFAULT '')""")
    db.execute("INSERT OR IGNORE INTO overnight_settings(id) VALUES(1)")

def add_task(title, priority=1, owner="human", kind=""):
    if not isinstance(title,str) or not 3 <= len(title.strip()) <= 120:
        raise ValueError("Title must contain 3–120 characters")
    if priority not in PRIORITIES or owner not in OWNERS:
        raise ValueError("Invalid priority or owner")
    if kind and (owner != "luna" or kind not in ALLOWED):
        raise ValueError("Only allowlisted jobs may be delegated to Luna")
    with core.connect() as db:
        _setup(db)
        cur=db.execute("INSERT INTO development_backlog(title,priority,owner,kind,created_at) VALUES(?,?,?,?,?)",
                       (title.strip(),priority,owner,kind,_now()))
        return cur.lastrowid

def tasks():
    with core.connect() as db:
        _setup(db)
        rows=db.execute("SELECT id,title,priority,owner,kind,state,job_id FROM development_backlog ORDER BY priority,id").fetchall()
    return [dict(zip(("id","title","priority","owner","kind","state","job_id"),row)) for row in rows]

def settings():
    with core.connect() as db:
        _setup(db)
        row=db.execute("SELECT enabled,max_jobs,max_model_tokens,used_model_tokens,session_day FROM overnight_settings WHERE id=1").fetchone()
    return dict(zip(("enabled","max_jobs","max_model_tokens","used_model_tokens","session_day"),row))

def configure(enabled, max_jobs=3, max_model_tokens=0):
    if not isinstance(enabled,bool) or type(max_jobs) is not int or not 1 <= max_jobs <= 10:
        raise ValueError("Invalid overnight settings")
    if type(max_model_tokens) is not int or not 0 <= max_model_tokens <= 100000:
        raise ValueError("Invalid model token budget")
    with core.connect() as db:
        _setup(db)
        db.execute("UPDATE overnight_settings SET enabled=?,max_jobs=?,max_model_tokens=? WHERE id=1",
                   (int(enabled),max_jobs,max_model_tokens))
    return settings()

def record_model_tokens(count):
    """Conservative local accounting hook. Not yet wired to provider usage."""
    if type(count) is not int or count < 0:
        raise ValueError("Invalid token count")
    with core.connect() as db:
        _setup(db)
        db.execute("UPDATE overnight_settings SET used_model_tokens=used_model_tokens+? WHERE id=1",(count,))

def tick():
    """Queue at most one approved, allowlisted task per tick. Never executes model code."""
    day=datetime.now(timezone.utc).date().isoformat()
    with core.connect() as db:
        _setup(db)
        enabled,cap,token_cap,used,session_day=db.execute(
            "SELECT enabled,max_jobs,max_model_tokens,used_model_tokens,session_day FROM overnight_settings WHERE id=1").fetchone()
        if session_day != day:
            db.execute("UPDATE overnight_settings SET session_day=?,used_model_tokens=0 WHERE id=1",(day,))
            used=0
        if not enabled:
            return {"queued":False,"reason":"paused"}
        if token_cap and used >= token_cap:
            return {"queued":False,"reason":"token_budget"}
        rows=db.execute("SELECT id,title,kind FROM development_backlog WHERE owner='luna' AND state='open' AND kind!='' ORDER BY priority,id").fetchall()
        queued_today=db.execute("""SELECT COUNT(*) FROM development_backlog b JOIN work_items w ON w.id=b.job_id
                                   WHERE substr(w.created_at,1,10)=?""",(day,)).fetchone()[0]
        if queued_today >= cap:
            return {"queued":False,"reason":"job_budget"}
        if not rows:
            return {"queued":False,"reason":"no_eligible_tasks"}
        task_id,title,kind=rows[0]
        # This transaction commits before creating a job; retry-safe reconciliation below.
        db.execute("UPDATE development_backlog SET state='dispatching' WHERE id=? AND state='open'",(task_id,))
    try:
        job_id=jobs.create_job(kind,title)
    except Exception:
        with core.connect() as db:
            db.execute("UPDATE development_backlog SET state='attention' WHERE id=? AND state='dispatching'",(task_id,))
        raise
    with core.connect() as db:
        db.execute("UPDATE development_backlog SET state='queued',job_id=? WHERE id=? AND state='dispatching'",(job_id,task_id))
    return {"queued":True,"task_id":task_id,"job_id":job_id}

def reconcile():
    with core.connect() as db:
        _setup(db)
        db.execute("UPDATE development_backlog SET state='attention' WHERE state='dispatching'")
        db.execute("""UPDATE development_backlog SET state=(
           SELECT CASE WHEN w.state='completed' THEN 'completed'
                       WHEN w.state IN ('attention','cancelled') THEN 'attention'
                       ELSE 'queued' END FROM work_items w WHERE w.id=development_backlog.job_id)
           WHERE state='queued' AND job_id IS NOT NULL
           AND EXISTS (SELECT 1 FROM work_items w WHERE w.id=development_backlog.job_id
                       AND w.state IN ('completed','attention','cancelled'))""")
