"""Bounded independent maintenance; no code writes, shell, or model calls."""
from datetime import datetime, timezone, timedelta
from luna import core, jobs, model_autonomy

ROUTINES = {
    "project_health": {"interval_minutes": 30, "priority": "high"},
    "development_plan": {"interval_minutes": 360, "priority": "normal"},
    "self_improvement": {"interval_minutes": 720, "priority": "normal"},
    "autonomous_draft": {"interval_minutes": 360, "priority": "normal"},
}
def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS autopilot_config
      (id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 1,
       updated_at TEXT NOT NULL DEFAULT '')""")
    db.execute("INSERT OR IGNORE INTO autopilot_config(id,enabled) VALUES(1,1)")
    db.execute("""CREATE TABLE IF NOT EXISTS autopilot_runs
      (kind TEXT PRIMARY KEY, last_queued_at TEXT NOT NULL)""")

def status():
    drafting=model_autonomy.status()
    with core.connect() as db:
        _setup(db)
        enabled=bool(db.execute("SELECT enabled FROM autopilot_config WHERE id=1").fetchone()[0])
        recent=dict(db.execute("SELECT kind,last_queued_at FROM autopilot_runs").fetchall())
    return {"enabled":enabled, "scope":"predefined low-risk local jobs only",
            "auto_apply":False,
            "model_calls":drafting["eligible"],
            "automatic_cloud_calls":False,
            "drafting":drafting,
            "routines":[{"kind":kind,"interval_minutes":rule["interval_minutes"],
                         "priority":rule["priority"],"last_queued_at":recent.get(kind)}
                        for kind,rule in ROUTINES.items()]}

def configure(enabled):
    if type(enabled) is not bool:
        raise ValueError("Enabled must be a boolean")
    with core.connect() as db:
        _setup(db)
        db.execute("UPDATE autopilot_config SET enabled=?,updated_at=? WHERE id=1",
                   (int(enabled),datetime.now(timezone.utc).isoformat()))
    return status()

def tick(now=None):
    """Queue bounded work only when due. Never run user-supplied commands."""
    now=now or datetime.now(timezone.utc)
    queued=[]
    drafting=model_autonomy.status()
    with core.connect() as db:
        _setup(db)
        if not db.execute("SELECT enabled FROM autopilot_config WHERE id=1").fetchone()[0]:
            return {"queued":queued,"reason":"paused"}
        for kind,rule in ROUTINES.items():
            if kind=="autonomous_draft" and not (
                    drafting["eligible"] and drafting["remaining_today"]>=2):
                continue
            previous=db.execute("SELECT last_queued_at FROM autopilot_runs WHERE kind=?",(kind,)).fetchone()
            if previous and now-datetime.fromisoformat(previous[0]) < timedelta(minutes=rule["interval_minutes"]):
                continue
            # Use the same transaction: opening another writer here locks SQLite.
            jobs._setup(db)
            existing=db.execute(
                "SELECT id FROM work_items WHERE kind=? AND state IN ('queued','running') LIMIT 1",
                (kind,)).fetchone()
            if existing:
                continue
            stamp=datetime.now(timezone.utc).isoformat()
            cur=db.execute(
                """INSERT INTO work_items(kind,title,detail,state,created_at,updated_at)
                   VALUES(?,?,'','queued',?,?)""",
                (kind,"Autopilot: "+kind.replace("_"," ").title(),stamp,stamp))
            result={"id":cur.lastrowid,"created":True}
            if result["created"]:
                db.execute("INSERT INTO autopilot_runs(kind,last_queued_at) VALUES(?,?) ON CONFLICT(kind) DO UPDATE SET last_queued_at=excluded.last_queued_at",
                           (kind,now.isoformat()))
                queued.append({"kind":kind,"job_id":result["id"]})
    return {"queued":queued,"reason":"ok","dispatch_policy":"allowlisted_only","auto_apply":False}
