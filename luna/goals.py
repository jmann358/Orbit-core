"""Persistent, supervised delegation of narrowly allowlisted goal steps.

Goal approval authorizes only the immutable step list. Model-produced text,
titles, and job details never become commands, destinations or permissions.
"""
from datetime import datetime, timezone
import hashlib
import json
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
ACTIVE_STATES = ("approved", "running", "paused", "waiting_budget", "waiting_queue", "cancel_requested")


def _setup(db):
    if not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")
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
    columns = {row[1] for row in db.execute("PRAGMA table_info(agent_goals)")}
    for name, declaration in (
        ("revision", "INTEGER NOT NULL DEFAULT 1"),
        ("predecessor_id", "INTEGER"), ("successor_id", "INTEGER"),
        ("plan_json", "TEXT NOT NULL DEFAULT ''"),
        ("plan_digest", "TEXT NOT NULL DEFAULT ''"),
        ("approval_digest", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in columns:
            db.execute("ALTER TABLE agent_goals ADD COLUMN " + name + " " + declaration)
    # Legacy approvals have no frozen plan to compare against. Preserve their
    # history, but stop future claims rather than fabricating a scoped grant.
    for ident, state in db.execute(
        "SELECT id,state FROM agent_goals WHERE plan_json=''"
    ).fetchall():
        _freeze_plan(db, ident)
        if state in ACTIVE_STATES:
            _state(db, ident, "attention", "legacy_approval_unbound",
                   "Prior approval lacks an immutable plan; review a replacement before continuing")


def _contract(db, goal_id):
    row = db.execute("SELECT objective,revision,predecessor_id FROM agent_goals WHERE id=?",
                     (goal_id,)).fetchone()
    if row is None:
        return None
    steps = db.execute("SELECT position,kind FROM agent_goal_steps WHERE goal_id=? ORDER BY position",
                       (goal_id,)).fetchall()
    return {
        "schema_version": 1, "goal_id": goal_id, "objective": row[0],
        "revision": row[1], "predecessor_id": row[2],
        "steps": [{"position": position, "kind": kind,
                   "max_attempts": jobs._attempt_limit(kind)} for position, kind in steps],
        "scope": "Fixed allowlisted diagnostics and non-executing planning only",
        "limits": {"max_steps": MAX_STEPS, "daily_dispatch_limit": MAX_DAILY_DISPATCHES,
                   "paid_calls": False, "generated_code_execution": False,
                   "permission_expansion": False},
        "evidence_policy": "Worker reports are not independently verified outcomes",
    }


def _serialize(contract):
    return json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _freeze_plan(db, goal_id):
    frozen = _serialize(_contract(db, goal_id))
    digest = hashlib.sha256(frozen.encode()).hexdigest()
    db.execute("UPDATE agent_goals SET plan_json=?,plan_digest=? WHERE id=?",
               (frozen, digest, goal_id))


def plan_integrity(db, goal_id, *, approved=False):
    """Compare source rows to the frozen proposal; digest is not authentication."""
    row = db.execute("SELECT plan_json,plan_digest,approval_digest FROM agent_goals WHERE id=?",
                     (goal_id,)).fetchone()
    if not row or not row[0] or not row[1]:
        return False
    frozen, digest, authorization = row
    return (hashlib.sha256(frozen.encode()).hexdigest() == digest
            and _serialize(_contract(db, goal_id)) == frozen
            and (not approved or authorization == digest))


def _expected(record, revision, digest):
    if record is None or revision != record["revision"] or digest != record["plan_digest"]:
        raise ValueError("Mission revision changed; refresh the displayed plan")


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
        "('approved','running','paused','waiting_budget','waiting_queue','cancel_requested')"
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


def _validate_proposal(objective, steps):
    if not isinstance(objective, str) or not 5 <= len(objective.strip()) <= 500:
        raise ValueError("Invalid objective")
    if (not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS
            or any(type(s) is not str or s not in ALLOWED_STEPS for s in steps)):
        raise ValueError("Steps must be bounded allowlisted actions")
    agent_registry.validate_plan(steps)


def _propose(db, objective, steps, *, revision=1, predecessor_id=None):
    waiting = db.execute("SELECT COUNT(*) FROM agent_goals WHERE state='proposed'").fetchone()[0]
    if waiting >= MAX_OUTSTANDING_PROPOSALS:
        raise ValueError("Too many proposed goals; review the queue")
    stamp = core.timestamp()
    cur = db.execute(
        "INSERT INTO agent_goals(objective,created_at,updated_at,revision,predecessor_id) "
        "VALUES(?,?,?,?,?)", (objective.strip(), stamp, stamp, revision, predecessor_id),
    )
    ident = cur.lastrowid
    for i, kind in enumerate(steps):
        db.execute("INSERT INTO agent_goal_steps(goal_id,position,kind) VALUES(?,?,?)", (ident, i, kind))
    _freeze_plan(db, ident)
    _event(db, ident, "proposed", "Pending owner review of revision " + str(revision))
    return ident


def propose_goal(objective, steps):
    _validate_proposal(objective, steps)
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        return _propose(db, objective, steps)


def propose_from_recipe(recipe_id, objective):
    proposal = goal_recipes.preview(recipe_id, objective)
    return propose_goal(objective, [step["kind"] for step in proposal["steps"]])


def _goal(db, goal_id):
    row = db.execute(
        "SELECT id,objective,state,created_at,updated_at,revision,predecessor_id,successor_id,"
        "plan_digest,approval_digest,plan_json "
        "FROM agent_goals WHERE id=?", (goal_id,),
    ).fetchone()
    if row is None:
        return None
    steps = db.execute(
        "SELECT id,position,kind,state,job_id FROM agent_goal_steps "
        "WHERE goal_id=? ORDER BY position", (goal_id,),
    ).fetchall()
    approval = db.execute(
        "SELECT id FROM agent_goal_events WHERE goal_id=? AND event='approved' AND details=? ORDER BY id LIMIT 1",
        (goal_id, "Explicit owner decision for revision " + str(row[5]) + "; plan " + row[8]),
    ).fetchone()
    return {
        "id": row[0], "objective": row[1], "state": row[2],
        "created_at": row[3], "updated_at": row[4],
        "revision": row[5], "predecessor_id": row[6], "successor_id": row[7],
        "plan_digest": row[8], "approval_digest": row[9], "plan": json.loads(row[10]),
        "approval_event_id": approval[0] if approval else None,
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


def decide_goal(goal_id, approve, *, expected_revision=None, expected_digest=None):
    """Atomic owner decision; no approval can expand a specialist's tools."""
    if type(approve) is not bool:
        raise ValueError("Approve must be boolean")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        record = _goal(db, goal_id)
        if record is None or record["state"] != "proposed":
            return False
        # HTTP callers must supply both values. Trusted in-process callers
        # retain the existing explicit-decision interface for fixed proposals.
        if expected_revision is not None or expected_digest is not None:
            _expected(record, expected_revision, expected_digest)
        if not plan_integrity(db, goal_id):
            raise ValueError("Mission no longer matches its frozen plan")
        if approve:
            budget = _budget(db)
            if budget["active_goals"] >= MAX_ACTIVE_GOALS:
                raise ValueError("Active goal limit reached; pause or finish work")
            agent_registry.validate_plan([s["kind"] for s in record["steps"]])
        new_state = "approved" if approve else "rejected"
        if approve:
            db.execute("UPDATE agent_goals SET approval_digest=plan_digest WHERE id=?", (goal_id,))
        _state(db, goal_id, new_state, new_state,
               "Explicit owner decision for revision " + str(record["revision"]) +
               "; plan " + record["plan_digest"])
        return True


def replace_goal(goal_id, objective, steps, *, expected_revision, expected_digest):
    """Create a linked unapproved revision; never rewrite an earlier plan."""
    _validate_proposal(objective, steps)
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        jobs._setup(db)
        old = _goal(db, goal_id)
        _expected(old, expected_revision, expected_digest)
        if old["state"] not in ("proposed", "approved", "running", "paused", "waiting_budget", "waiting_queue", "attention"):
            raise ValueError("This mission revision cannot be replaced")
        unresolved = db.execute(
            "SELECT 1 FROM agent_goal_steps s JOIN work_items w ON w.id=s.job_id "
            "WHERE s.goal_id=? AND (w.state='running' OR "
            "(w.state='attention' AND w.result='Interrupted by server restart')) LIMIT 1",
            (goal_id,),
        ).fetchone()
        if unresolved:
            _state(db, goal_id, "paused", "modification_waiting",
                   "Future claims paused; reconcile in-flight or interrupted work before replacement")
            return {**_goal(db, goal_id), "replacement_created": False,
                    "requires_reconciliation": True}
        _reconcile_finished_steps(db, goal_id)
        _state(db, goal_id, "superseded", "superseded", "Replacement requires a new owner approval")
        for step in old["steps"]:
            if step["job_id"] is not None:
                changed = db.execute(
                    "UPDATE work_items SET state='cancelled',next_attempt_at='',updated_at=? "
                    "WHERE id=? AND state IN ('queued','retry_wait')",
                    (core.timestamp(), step["job_id"]),
                )
                if changed.rowcount:
                    jobs._event(db, step["job_id"], "cancelled", "Mission revision superseded")
                    db.execute("UPDATE agent_goal_steps SET state='cancelled' WHERE id=?", (step["id"],))
        successor = _propose(db, objective, steps, revision=old["revision"] + 1, predecessor_id=goal_id)
        db.execute("UPDATE agent_goals SET successor_id=? WHERE id=?", (successor, goal_id))
        _event(db, goal_id, "replacement_proposed", "Successor goal #" + str(successor))
        return {**_goal(db, successor), "replacement_created": True,
                "requires_reconciliation": False}


def _reconcile_finished_steps(db, goal_id):
    """Retain observed child outcomes when ending a revision early."""
    for step_id, job_state in db.execute(
        "SELECT s.id,w.state FROM agent_goal_steps s JOIN work_items w ON w.id=s.job_id "
        "WHERE s.goal_id=? AND s.state='running' AND w.state IN ('completed','attention','cancelled')",
        (goal_id,),
    ).fetchall():
        db.execute("UPDATE agent_goal_steps SET state=? WHERE id=?", (job_state, step_id))
        _event(db, goal_id, "step_reconciled", "Step " + str(step_id) + ": " + job_state)


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
    in_flight = any(step["job"] and step["job"]["state"] == "running" for step in details)
    uncertain = any(step["job"] and step["job"]["state"] == "attention"
                    and step["job"]["result"] == "Interrupted by server restart" for step in details)
    state = goal["state"]
    blocked = (
        "cancel_requested_waiting_for_outcome" if state == "cancel_requested" else
        "needs_owner_review" if state == "attention" else
        "owner_paused" if state == "paused" else
        "global_worker_paused" if paused and state in ACTIVE_STATES else
        "daily_dispatch_budget" if state == "waiting_budget" else
        "queue_capacity" if state == "waiting_queue" else None
    )
    return {
        "id": goal_id, "objective": goal["objective"], "state": state,
        "revision": goal["revision"], "plan_digest": goal["plan_digest"],
        "approval_digest": goal["approval_digest"], "plan": goal["plan"],
        "approval_event_id": goal["approval_event_id"],
        "created_at": goal["created_at"], "updated_at": goal["updated_at"],
        "predecessor_id": goal["predecessor_id"], "successor_id": goal["successor_id"],
        "completed_steps": completed, "total_steps": len(details),
        "next_step": next((s["position"]+1 for s in details
                           if s["state"] != "completed"), None),
        "requires_attention": state == "attention",
        "in_flight": in_flight, "outcome_uncertain": uncertain,
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
        if action == "resume" and not plan_integrity(db, goal_id, approved=True):
            return False
        if action == "cancel" and state not in (
            "proposed", "approved", "running", "paused",
            "waiting_budget", "waiting_queue", "attention"
        ):
            return False
        target = {"pause": "paused", "resume": "approved",
                  "cancel": "cancelled"}[action]
        if action == "cancel" and db.execute(
            "SELECT 1 FROM agent_goal_steps s JOIN work_items w ON w.id=s.job_id "
            "WHERE s.goal_id=? AND (w.state='running' OR "
            "(w.state='attention' AND w.result='Interrupted by server restart')) LIMIT 1",
            (goal_id,),
        ).fetchone():
            target = "cancel_requested"
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
        # Cancellation reconciliation never dispatches anything, including
        # when the global worker is paused. Interrupted outcomes remain unknown.
        for (goal_id,) in db.execute(
            "SELECT id FROM agent_goals WHERE state='cancel_requested'"
        ).fetchall():
            unresolved = db.execute(
                "SELECT 1 FROM agent_goal_steps s JOIN work_items w ON w.id=s.job_id "
                "WHERE s.goal_id=? AND (w.state='running' OR "
                "(w.state='attention' AND w.result='Interrupted by server restart')) LIMIT 1",
                (goal_id,),
            ).fetchone()
            if not unresolved:
                _reconcile_finished_steps(db, goal_id)
                _state(db, goal_id, "cancelled", "cancellation_reconciled",
                       "In-flight result recorded; remaining steps cancelled")
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
            if not plan_integrity(db, goal_id, approved=True):
                _state(db, goal_id, "attention", "authorization_denied",
                       "Approved revision no longer matches its frozen plan")
                continue
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
                    revision, digest = db.execute(
                        "SELECT revision,approval_digest FROM agent_goals WHERE id=?", (goal_id,)
                    ).fetchone()
                    cur = db.execute(
                        "INSERT INTO work_items(kind,title,detail,state,"
                        "created_at,updated_at,max_attempts,goal_id,goal_revision,goal_plan_digest) "
                        "VALUES(?,?,'','queued',?,?,?,?,?,?)",
                        (kind, "Goal " + str(goal_id) + ": " +
                         ALLOWED_STEPS[kind], stamp, stamp,
                         jobs._attempt_limit(kind), goal_id, revision, digest),
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
