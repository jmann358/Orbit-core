"""Local self-improvement planner. Proposals only; no generated code execution."""
from datetime import datetime, timezone
from luna import core

ROADMAP = (
    ("Secure phone access", "Add authenticated remote access with explicit pairing; keep loopback-only until tested."),
    ("Goal decomposition", "Turn a requested goal into bounded subtasks with separate permissions and progress."),
    ("Durable scheduler", "Persist scheduling settings and implement idempotent task leases and pause controls."),
    ("Draft change format", "Require target file allowlists, base revision and a reviewable patch format."),
    ("GitHub feedback bridge", "Exchange authenticated development status without publishing private data."),
)

def next_improvement():
    """Select next unproposed roadmap item; no model output is treated as code."""
    with core.connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS improvement_proposals (
            id INTEGER PRIMARY KEY, title TEXT UNIQUE NOT NULL, description TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL)""")
        existing={r[0] for r in db.execute("SELECT title FROM improvement_proposals").fetchall()}
        for title, description in ROADMAP:
            if title not in existing:
                now=datetime.now(timezone.utc).isoformat()
                cur=db.execute("INSERT INTO improvement_proposals(title,description,status,created_at) VALUES(?,?,'proposed',?)",
                               (title,description,now))
                return {"id":cur.lastrowid,"title":title,"description":description,"status":"proposed"}
    return None

def list_improvements():
    with core.connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS improvement_proposals (
            id INTEGER PRIMARY KEY, title TEXT UNIQUE NOT NULL, description TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL)""")
        rows=db.execute("SELECT id,title,description,status,created_at FROM improvement_proposals ORDER BY id DESC LIMIT 50").fetchall()
    return [dict(zip(("id","title","description","status","created_at"),r)) for r in rows]
