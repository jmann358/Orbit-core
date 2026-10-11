"""Persistent, supervised delegation of narrowly allowlisted goal steps.

Goal approval authorizes only the immutable step list. Model-produced text,
titles, and job details never become commands, destinations or permissions.
"""
from datetime import datetime, timezone
from luna import core, jobs, agent_registry, goal_recipes

ALLOWED_STEPS = {
    "project_health": "Read-only local project health",
    "github_status": "Read-only GitHub status",
    "development_plan": "Prepare a non-executing development plan",
}
MAX_STEPS = 5
MAX_ACTIVE_GOALS = 8
MAX_DAILY_DISPATCHES = 12
MAX_OUTSTANDING_PROPOSALS = 60
ACTIVE_STATES = ("approved", "running", "paused", "waiting_budget", "waiting_queue")


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS agent_goals (
        id INTEGER PRIMARY KEY, objective TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'proposed',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS agent_goal_steps (
        id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL,
        position INTEGER NOT NULL, kind TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending', job_id INTEGER,
        FOREIGN KEY(goal_id) REFERENCES agent_goals(id))""")
    db.execute("""CREATE TABLE IF NOT EXISTS agent_goal_events (
        id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL,
        event TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS agent_goal_events_idx ON "
               "agent_goal_events(goal_id,id)")


def _event(db, goal_id, event, details=""):
    db.execute(
        "INSERT INTO agent_goal_events(goal_id,event,details,created_at) "
        "VALUES(?,?,?,?)",
        (goal_id, event, str(details)[:400], core.timestamp()),
    )


def _state(db, goal_id, state, event=None, note=""):
    prior = db.execute("SELECT state FROM agent_goals WHERE id=?",
                       (goal_id,)).fetchone()
    if prior is not None and prior[0] != state:
        db.execute("UPDATE agent_goals SET state=?,updated_at=? WHERE id=?",
                   (state, core.timestamp(), goal_id))
        if event:
            _event(db, goal_id, event, note)
        return True
    return False


def _day():
    return datetime.now(timezone.utc).date().isoformat()


def _budget(db):
    jobs._setup(db)
    used = db.execute(
        """SELECT COUNT(*) FROM agent_goal_steps s
           JOIN work_items w ON w.id=s.job_id
           WHERE substr(w.created_at,1,10)=?""", (_day(),),
    ).fetchone()[0]
    active = db.execute(
        "SELECT COUNT(*) FROM agent_goals WHERE state IN "
        "('approved','running','paused','waiting_budget','waiting_queue')"
    ).fetchone()[0]
    return {
        "day_utc": _day(), "dispatched_today": used,
        "daily_dispatch_limit": MAX_DAILY_DISPATCHES,
        "daily_remaining": max(0, MAX_DAILY_DISPATCHES-used),
        "active_goals": active, "active_goal_limit": MAX_ACTIVE_GOALS,
        "max_steps_per_goal": MAX_STEPS, "cost_budget": "no model calls",
    }


def delegation_status():
    with core.connect() as db:
        _setup(db)
        return _budget(db)


def propose_goal(objective, steps):
    if not isinstance(objective, str) or not 5 <= len(objective.strip()) <= 500:
        raise ValueError("Invalid objective")
    if (not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS
            or any(type(s) is not str or s not in ALLOWED_STEPS for s in steps)):
        raise ValueError("Steps must be bounded allowlisted actions")
    agent_registry.validate_plan(steps)
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        waiting = db.execute(
            "SELECT COUNT(*) FROM agent_goals WHERE state='proposed'"
        ).fetchone()[0]
        if waiting >= MAX_OUTSTANDING_PROPOSALS:
            raise ValueError("Too many proposed goals; review the queue")
        stamp = core.timestamp()
        cur = db.execute(
            "INSERT INTO agent_goals(objective,created_at,updated_at) "
            "VALUES(?,?,?)", (objective.strip(), stamp, stamp),
        )
        ident = cur.lastrowid
        for i, kind in enumerate(steps):
            db.execute("INSERT INTO agent_goal_steps(goal_id,position,kind) "
                       "VALUES(?,?,?)", (ident, i, kind))
        _event(db, ident, "proposed", "Pending owner review")
        return ident


def propose_from_recipe(recipe_id, objective):
    proposal = goal_recipes.preview(recipe_id, objective)
    return propose_goal(objective, [step["kind"] for step in proposal["steps"]])


def _goal(db, goal_id):
    row = db.execute(
        "SELECT id,objective,state,created_at,updated_at "
        "FROM agent_goals WHERE id=?", (goal_id,),
    ).fetchone()
    if row is None:
        return None
    steps = db.execute(
        "SELECT id,position,kind,state,job_id FROM agent_goal_steps "
        "WHERE goal_id=? ORDER BY position", (goal_id,),
    ).fetchall()
    return {
        "id": row[0], "objective": row[1], "state": row[2],
        "created_at": row[3], "updated_at": row[4],
        "steps": [dict(zip(("id","position","kind","state","job_id"), s))
                  for s in steps],
    }


def list_goals(limit=30):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("Invalid listing limit")
    with core.connect() as db:
        _setup(db)
        identifiers = db.execute(
            "SELECT id FROM agent_goals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_goal(db, row[0]) for row in identifiers]


def decide_goal(goal_id, approve):
    """Atomic owner decision; no approval can expand a specialist's tools."""
    if type(approve) is not bool:
        raise ValueError("Approve must be boolean")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        record = _goal(db, goal_id)
        if record is None or record["state"] != "proposed":
            return False
        if approve:
            budget = _budget(db)
            if budget["active_goals"] >= MAX_ACTIVE_GOALS:
                raise ValueError("Active goal limit reached; pause or finish work")
            agent_registry.validate_plan([s["kind"] for s in record["steps"]])
        new_state = "approved" if approve else "rejected"
        _state(db, goal_id, new_state, new_state,
               "Explicit owner decision")
        return True


def _events(db, goal_id, limit=25):
    rows = db.execute(
        "SELECT id,event,details,created_at FROM agent_goal_events "
        "WHERE goal_id=? ORDER BY id DESC LIMIT ?", (goal_id, limit),
    ).fetchall()
    return [
        dict(zip(("id","event","details","created_at"), row))
        for row in reversed(rows)
    ]


def goal_report(goal_id):
    """Actual outcomes and audit, not predicted or fabricated model progress."""
    with core.connect() as db:
        _setup(db)
        jobs._setup(db)
        goal = _goal(db, goal_id)
        if goal is None:
            return None
        details = []
        for step in goal["steps"]:
            record = None
            if step["job_id"] is not None:
                row = db.execute(
                    "SELECT id,state,result,attempt_count,max_attempts "
                    "FROM work_items WHERE id=?", (step["job_id"],),
                ).fetchone()
                if row:
                    record = dict(zip(
                        ("id","state","result","attempt_count","max_attempts"), row
                    ))
            # Older local database contents might have invalid values: show
            # the problem as data instead of crashing the whole dashboard.
            try:
                specialist = agent_registry.specialist_for(step["kind"])
            except ValueError:
                specialist = None
            details.append({
                **step, "label": ALLOWED_STEPS.get(step["kind"], "Unknown action"),
                "specialist": specialist, "job": record,
            })
        budget = _budget(db)
        paused = not db.execute("SELECT enabled FROM worker_config WHERE id=1").fetchone()[0]
        events = _events(db, goal_id)
    completed = sum(step["state"] == "completed" for step in details)
    state = goal["state"]
    blocked = (
        "needs_owner_review" if state == "attention" else
        "owner_paused" if state == "paused" else
        "global_worker_paused" if paused and state in ACTIVE_STATES else
        "daily_dispatch_budget" if state == "waiting_budget" else
        "queue_capacity" if state == "waiting_queue" else None
    )
    return {
        "id": goal_id, "objective": goal["objective"], "state": state,
        "completed_steps": completed, "total_steps": len(details),
        "next_step": next((s["position"]+1 for s in details
                           if s["state"] != "completed"), None),
        "requires_attention": state == "attention",
        "blocked_reason": blocked,
        "steps": details, "events": events, "delegation_budget": budget,
        "read_only": True,
    }


def control_goal(goal_id, action):
    """Pause, resume or cancel future claims; in-flight handlers may finish."""
    if action not in ("pause", "resume", "cancel"):
        raise ValueError("Unsupported goal action")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        jobs._setup(db)
        goal = _goal(db, goal_id)
        if goal is None:
            return False
        state = goal["state"]
        if action == "pause" and state not in (
            "approved", "running", "waiting_budget", "waiting_queue"
        ):
            return False
        if action == "resume" and state != "paused":
            return False
        if action == "cancel" and state not in (
            "proposed", "approved", "running", "paused",
            "waiting_budget", "waiting_queue", "attention"
        ):
            return False
        target = {"pause": "paused", "resume": "approved",
                  "cancel": "cancelled"}[action]
        _state(db, goal_id, target, target, "Owner requested " + action)
        if action == "cancel":
            for step in goal["steps"]:
                if step["state"] == "pending":
                    db.execute("UPDATE agent_goal_steps SET state='cancelled' "
                               "WHERE id=?", (step["id"],))
                elif step["state"] == "running" and step["job_id"] is not None:
                    changed = db.execute(
                        "UPDATE work_items SET state='cancelled',"
                        "next_attempt_at='',updated_at=? WHERE id=? "
                        "AND state IN ('queued','retry_wait')",
                        (core.timestamp(), step["job_id"]),
                    )
                    if changed.rowcount:
                        jobs._event(db, step["job_id"], "cancelled",
                                    "Owner cancelled goal")
                        db.execute(
                            "UPDATE agent_goal_steps SET state='cancelled' "
                            "WHERE id=?", (step["id"],),
                        )
        return True


def advance_goals():
    """Advance at most one ready step per goal in one SQLite transaction.

    Crash-safe queue creation, sequential dependencies, capability validation
    and daily dispatch limits. Never implicitly approve, retry or execute code.
    """
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        jobs._setup(db)
        if not db.execute(
            "SELECT enabled FROM worker_config WHERE id=1"
        ).fetchone()[0]:
            return
        budget = _budget(db)
        used = budget["dispatched_today"]
        ids = db.execute(
            "SELECT id FROM agent_goals WHERE state IN "
            "('approved','running','waiting_budget','waiting_queue') "
            "ORDER BY id LIMIT 20"
        ).fetchall()
        for (goal_id,) in ids:
            steps = db.execute(
                "SELECT id,kind,state,job_id FROM agent_goal_steps "
                "WHERE goal_id=? ORDER BY position", (goal_id,),
            ).fetchall()
            waiting = False
            failed = False
            new_state = "completed"
            for step_id, kind, state, job_id in steps:
                if state == "completed":
                    continue
                if state == "running":
                    row = db.execute(
                        "SELECT state FROM work_items WHERE id=?", (job_id,)
                    ).fetchone()
                    if row is None or row[0] in ("attention", "cancelled"):
                        db.execute("UPDATE agent_goal_steps SET state='attention' "
                                   "WHERE id=?", (step_id,))
                        failed = True
                    elif row[0] == "completed":
                        db.execute("UPDATE agent_goal_steps SET state='completed' "
                                   "WHERE id=?", (step_id,))
                        _event(db, goal_id, "step_completed",
                               "Step " + str(step_id) + " completed")
                        continue
                    else:
                        waiting = True
                    break
                if state in ("attention", "cancelled"):
                    failed = True
                    break
                if state == "pending":
                    try:
                        if kind not in ALLOWED_STEPS:
                            raise ValueError("Unapproved job kind")
                        specialist = agent_registry.specialist_for(kind)
                    except ValueError:
                        db.execute("UPDATE agent_goal_steps SET state='attention' "
                                   "WHERE id=?", (step_id,))
                        failed = True
                        break
                    if used >= MAX_DAILY_DISPATCHES:
                        new_state = "waiting_budget"
                        waiting = True
                        break
                    if jobs._active_count(db) >= jobs.MAX_ACTIVE:
                        new_state = "waiting_queue"
                        waiting = True
                        break
                    stamp = core.timestamp()
                    cur = db.execute(
                        "INSERT INTO work_items(kind,title,detail,state,"
                        "created_at,updated_at,max_attempts) "
                        "VALUES(?,?,'','queued',?,?,?)",
                        (kind, "Goal " + str(goal_id) + ": " +
                         ALLOWED_STEPS[kind], stamp, stamp,
                         jobs._attempt_limit(kind)),
                    )
                    jobs._event(db, cur.lastrowid, "queued",
                                "Approved goal #" + str(goal_id) +
                                " delegated to " + specialist, stamp)
                    db.execute(
                        "UPDATE agent_goal_steps SET state='running',job_id=? "
                        "WHERE id=?", (cur.lastrowid, step_id),
                    )
                    _event(db, goal_id, "dispatched",
                           "Step " + str(step_id) + ": " + specialist +
                           " -> job #" + str(cur.lastrowid))
                    used += 1
                    waiting = True
                    new_state = "running"
                    break
            if failed:
                _state(db, goal_id, "attention", "needs_attention",
                       "Stopped for owner review; no replay")
            elif waiting:
                if new_state == "completed":
                    new_state = "running"
                _state(db, goal_id, new_state, new_state if new_state.startswith("waiting_") else None,
                       "Dispatch deferred by safe capacity limit")
            else:
                _state(db, goal_id, "completed", "completed",
                       "Every approved step completed")
