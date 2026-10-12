"""Owner-approved specialist agents with real bounded tasks.

An agent is a persistent role plus a scoped task queue. The worker can run
read-only project checks, or an explicitly enabled model can prepare a
non-executing code review / plan. These are not OS users, subprocesses, shells,
network-capable tools, or independently permissioned providers.
"""
from datetime import datetime, timezone
import re
from luna import core

MAX_AGENTS = 8
MAX_PENDING = 4
MAX_QUEUED_TASKS = 16
MAX_TASKS_PER_AGENT = 4
MODEL_CALLS_PER_DAY = 4

TEMPLATES = {
    "developer": {
        "label": "Development Helper",
        "purpose": "Inspect ORBIT and suggest small, reviewable source improvements",
        "capabilities": ("health", "code_review"),
        "first_tasks": ("health", "code_review"),
    },
    "inspector": {
        "label": "Project Inspector",
        "purpose": "Run read-only local project health checks",
        "capabilities": ("health",),
        "first_tasks": ("health",),
    },
    "planner": {
        "label": "Planning Assistant",
        "purpose": "Draft practical plans without executing code or accessing accounts",
        "capabilities": ("plan",),
        "first_tasks": ("plan",),
    },
}
MODEL_TASKS = frozenset(("code_review", "plan"))
DEFAULT_INSTRUCTIONS = {
    "health": "Check ORBIT's current local project health.",
    "code_review": "Review one existing ORBIT code module and propose up to three improvements.",
    "plan": "Suggest the next three bounded, actionable improvements to ORBIT.",
}
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9 _-]{1,39}\Z")


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS custom_agents (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
        template TEXT NOT NULL, purpose TEXT NOT NULL,
        status TEXT NOT NULL, created_at TEXT NOT NULL, approved_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS custom_agent_tasks (
        id INTEGER PRIMARY KEY, agent_id INTEGER NOT NULL, kind TEXT NOT NULL,
        instruction TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
        result TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, FOREIGN KEY(agent_id) REFERENCES custom_agents(id))""")
    db.execute("CREATE INDEX IF NOT EXISTS custom_agent_tasks_agent_id "
               "ON custom_agent_tasks(agent_id,id)")
    db.execute("""CREATE TABLE IF NOT EXISTS custom_agent_budget (
        id INTEGER PRIMARY KEY CHECK(id=1), day TEXT NOT NULL DEFAULT '',
        used INTEGER NOT NULL DEFAULT 0)""")
    db.execute("INSERT OR IGNORE INTO custom_agent_budget(id) VALUES(1)")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _agent(row):
    if row is None:
        return None
    record = dict(zip(("id", "name", "template", "purpose", "status",
                       "created_at", "approved_at"), row))
    profile = TEMPLATES.get(record["template"])
    record["capabilities"] = list(profile["capabilities"]) if profile else []
    record["no_code_execution"] = True
    record["no_credentials"] = True
    record["can_change_permissions"] = False
    record["can_spend_without_opt_in"] = False
    return record


def _task(row):
    if row is None:
        return None
    return dict(zip(("id", "agent_id", "kind", "instruction", "status",
                     "result", "created_at", "updated_at"), row))


AGENT_COLS = "id,name,template,purpose,status,created_at,approved_at"
TASK_COLS = "id,agent_id,kind,instruction,status,result,created_at,updated_at"


def _one(db, agent_id):
    return _agent(db.execute("SELECT " + AGENT_COLS + " FROM custom_agents WHERE id=?",
                             (agent_id,)).fetchone())


def get_agent(agent_id):
    if type(agent_id) is not int or agent_id < 1:
        return None
    with core.connect() as db:
        _setup(db)
        return _one(db, agent_id)


def list_agents(limit=30):
    with core.connect() as db:
        _setup(db)
        rows = db.execute("SELECT " + AGENT_COLS + " FROM custom_agents "
                          "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_agent(r) for r in rows]


def find_by_name(name):
    if not isinstance(name, str) or not name.strip():
        return None
    with core.connect() as db:
        _setup(db)
        row = db.execute("SELECT " + AGENT_COLS + " FROM custom_agents "
                         "WHERE name=? COLLATE NOCASE", (name.strip(),)).fetchone()
    return _agent(row)


def pending_agents():
    return [agent for agent in list_agents() if agent["status"] == "pending"]


def _name(name):
    if type(name) is not str or not _NAME.fullmatch(name.strip()):
        raise ValueError("Agent name must be 2–40 letters, digits, spaces, hyphens or underscores.")
    return " ".join(name.strip().split())


def propose_agent(name=None, template="developer", purpose=None):
    """Save an agent proposal; never activate without a separate owner action."""
    if type(template) is not str or template not in TEMPLATES:
        raise ValueError("Available roles: developer, inspector, planner.")
    profile = TEMPLATES[template]
    name = _name(name or profile["label"])
    purpose = purpose or profile["purpose"]
    if type(purpose) is not str or not 8 <= len(purpose.strip()) <= 300:
        raise ValueError("Agent purpose must be 8–300 characters.")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        if db.execute("SELECT COUNT(*) FROM custom_agents WHERE status IN "
                      "('active','paused','pending')").fetchone()[0] >= MAX_AGENTS:
            raise ValueError("Agent limit reached. Pause or review existing agents.")
        if db.execute("SELECT COUNT(*) FROM custom_agents WHERE status='pending'").fetchone()[0] >= MAX_PENDING:
            raise ValueError("Review existing agent proposals first.")
        if db.execute("SELECT 1 FROM custom_agents WHERE name=? COLLATE NOCASE",
                      (name,)).fetchone():
            raise ValueError("An agent with that name already exists.")
        stamp = _now()
        cur = db.execute("INSERT INTO custom_agents "
                         "(name,template,purpose,status,created_at) VALUES(?,?,?,'pending',?)",
                         (name, template, purpose.strip(), stamp))
        agent_id = cur.lastrowid
        return _one(db, agent_id)


def _queue(db, agent_id, kind, instruction):
    if type(instruction) is not str or not 8 <= len(instruction.strip()) <= 1000:
        raise ValueError("Agent task must be 8–1000 characters.")
    profile = db.execute("SELECT template,status FROM custom_agents WHERE id=?",
                         (agent_id,)).fetchone()
    if not profile or profile[1] != "active":
        raise ValueError("Agent must be approved and active before receiving tasks.")
    if kind not in TEMPLATES[profile[0]]["capabilities"]:
        raise ValueError("This agent is not approved for that task type.")
    if db.execute("SELECT COUNT(*) FROM custom_agent_tasks WHERE status IN "
                  "('queued','running')").fetchone()[0] >= MAX_QUEUED_TASKS:
        raise ValueError("Too many queued agent tasks.")
    if db.execute("SELECT COUNT(*) FROM custom_agent_tasks WHERE "
                  "agent_id=? AND status IN ('queued','running')",
                  (agent_id,)).fetchone()[0] >= MAX_TASKS_PER_AGENT:
        raise ValueError("That agent's task queue is full.")
    stamp = _now()
    cur = db.execute("INSERT INTO custom_agent_tasks "
                     "(agent_id,kind,instruction,status,created_at,updated_at) "
                     "VALUES(?,?,?,'queued',?,?)",
                     (agent_id, kind, instruction.strip(), stamp, stamp))
    return cur.lastrowid


def approve_agent(agent_id):
    """Atomic approval of a *fixed, visible* role and first safe tasks."""
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        agent = _one(db, agent_id)
        if not agent or agent["status"] != "pending":
            raise ValueError("Agent is not waiting for approval.")
        profile = TEMPLATES[agent["template"]]
        db.execute("UPDATE custom_agents SET status='active',approved_at=? "
                   "WHERE id=? AND status='pending'", (_now(), agent_id))
        task_ids = [_queue(db, agent_id, kind, DEFAULT_INSTRUCTIONS[kind])
                    for kind in profile["first_tasks"]]
    return {"agent": get_agent(agent_id), "first_task_ids": task_ids,
            "executed": False, "worker_required": True}


def reject_agent(agent_id):
    with core.connect() as db:
        _setup(db)
        cur = db.execute("UPDATE custom_agents SET status='rejected' WHERE "
                         "id=? AND status='pending'", (agent_id,))
        if not cur.rowcount:
            raise ValueError("Only pending agents can be rejected.")
    return get_agent(agent_id)


def set_paused(agent_id, paused):
    if type(paused) is not bool:
        raise ValueError("Paused must be true or false.")
    with core.connect() as db:
        _setup(db)
        old, new = ("active", "paused") if paused else ("paused", "active")
        cur = db.execute("UPDATE custom_agents SET status=? WHERE id=? AND status=?",
                         (new, agent_id, old))
        if not cur.rowcount:
            raise ValueError("Agent cannot make that transition.")
    return get_agent(agent_id)


def queue_task(agent_id, kind, instruction):
    if type(agent_id) is not int or agent_id < 1:
        raise ValueError("Unknown agent.")
    if type(kind) is not str:
        raise ValueError("Invalid task kind.")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        task_id = _queue(db, agent_id, kind, instruction)
    return get_task(task_id)


def get_task(task_id):
    if type(task_id) is not int or task_id < 1:
        return None
    with core.connect() as db:
        _setup(db)
        row = db.execute("SELECT " + TASK_COLS + " FROM custom_agent_tasks "
                         "WHERE id=?", (task_id,)).fetchone()
    return _task(row)


def list_tasks(limit=50, agent_id=None):
    with core.connect() as db:
        _setup(db)
        if agent_id is None:
            rows = db.execute("SELECT " + TASK_COLS + " FROM custom_agent_tasks "
                              "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = db.execute("SELECT " + TASK_COLS + " FROM custom_agent_tasks "
                              "WHERE agent_id=? ORDER BY id DESC LIMIT ?",
                              (agent_id, limit)).fetchall()
    return [_task(row) for row in rows]


def _model_ready():
    from luna.developer_model import configuration
    return configuration()["ready"]


def _budget(db):
    day = datetime.now(timezone.utc).date().isoformat()
    old, used = db.execute("SELECT day,used FROM custom_agent_budget WHERE id=1").fetchone()
    if old != day:
        db.execute("UPDATE custom_agent_budget SET day=?,used=0 WHERE id=1", (day,))
        used = 0
    return used


def status():
    agents = list_agents()
    tasks = list_tasks()
    from luna.developer_model import configuration
    model = configuration()
    return {
        "agents": agents, "tasks": tasks,
        "model_ready_unverified": model["ready"],
        "model_transport": model["transport"],
        "worker_runs_inside_luna": True,
        "arbitrary_tools": False,
        "automatic_model_budget_daily": MODEL_CALLS_PER_DAY,
    }


def recover_interrupted():
    """A model request interrupted by restart is not billed twice automatically."""
    with core.connect() as db:
        _setup(db)
        cur = db.execute("UPDATE custom_agent_tasks SET status='attention',"
                         "result='Worker interrupted; owner must review before another run',"
                         "updated_at=? WHERE status='running'", (_now(),))
        return cur.rowcount


def _claim():
    from luna import jobs
    if not jobs.worker_status()["enabled"]:
        return None
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        budget = _budget(db)
        rows = db.execute("SELECT t.id,t.agent_id,t.kind,t.instruction,a.status,a.template "
                          "FROM custom_agent_tasks t JOIN custom_agents a ON a.id=t.agent_id "
                          "WHERE t.status='queued' ORDER BY t.id LIMIT 20").fetchall()
        for ident, agent_id, kind, instruction, status, template in rows:
            if status != "active":
                continue
            if template not in TEMPLATES or kind not in TEMPLATES[template]["capabilities"]:
                db.execute("UPDATE custom_agent_tasks SET status='attention',"
                           "result='Agent permissions no longer match task',updated_at=? "
                           "WHERE id=?", (_now(), ident))
                continue
            if kind in MODEL_TASKS:
                if budget >= MODEL_CALLS_PER_DAY or not _model_ready():
                    continue
                # Charge before the call. A crash cannot silently replay it.
                db.execute("UPDATE custom_agent_budget SET used=used+1 WHERE id=1")
                budget += 1
            db.execute("UPDATE custom_agent_tasks SET status='running',updated_at=? "
                       "WHERE id=? AND status='queued'", (_now(), ident))
            return {"id": ident, "agent_id": agent_id, "kind": kind,
                    "instruction": instruction, "template": template}
    return None


def run_one():
    """Run at most one real task from the approved agent queue."""
    # Respect the existing Mac service backup gate before unattended work.
    import os
    if os.environ.get("LUNA_SERVICE_MODE") == "1":
        from luna.backup_schedule import maybe_backup
        from pathlib import Path
        try:
            maybe_backup(core.DB_PATH, root=Path(__file__).resolve().parents[1])
        except (OSError, ValueError):
            return None
    claimed = _claim()
    if claimed is None:
        return None
    success = False
    result = "Task could not be completed; inspect the agent's status."
    try:
        if claimed["kind"] == "health":
            # No model, shell, file writing or outgoing connection.
            from app import project_health
            report = project_health()
            failed = [x["name"] for x in report["checks"] if not x["ok"]]
            success = not failed
            result = ("Local project checks: " + str(report["passed"]) + "/"
                      + str(report["total"]) + " passed"
                      + (". Needs attention: " + ", ".join(failed) if failed else "."))
        else:
            from luna.custom_agent_model import ask_agent
            import asyncio
            result = asyncio.run(ask_agent(claimed["template"], claimed["kind"],
                                           claimed["instruction"]))
            success = True
    except Exception:
        # Never log raw provider errors, secrets, or file content.
        result = "Task failed; model or internal operation unavailable. No changes were made."
    with core.connect() as db:
        _setup(db)
        status = "completed" if success else "attention"
        db.execute("UPDATE custom_agent_tasks SET status=?,result=?,updated_at=? "
                   "WHERE id=? AND status='running'",
                   (status, str(result)[:5000], _now(), claimed["id"]))
    return get_task(claimed["id"])
