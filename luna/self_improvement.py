"""Local self-improvement planner. Proposals only; no generated code execution."""
from datetime import datetime, timezone
from luna import core

ROADMAP = (
    ("Development diagnostics", "Add a fixed-scope local project health report with clear failures, evidence, and suggested next actions."),
    ("Unified approval center", "Review proposed tasks, memory, notes, and code drafts in one mobile-friendly dashboard."),
    ("Safe patch review", "Require exact file targets, base revisions, bounded diffs, static checks and human approval before applying changes."),
    ("Conversation continuity", "Improve long-session summaries and retrieval of approved project context without automatically approving memories."),
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

def decide_improvement(improvement_id, decision):
    """A decision changes proposal status only, never code or permissions."""
    if decision not in ("approved", "rejected"):
        return False
    with core.connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS improvement_proposals (
            id INTEGER PRIMARY KEY, title TEXT UNIQUE NOT NULL, description TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL)""")
        cur = db.execute("UPDATE improvement_proposals SET status=? WHERE id=? AND status='proposed'",
                         (decision, improvement_id))
        return cur.rowcount == 1
