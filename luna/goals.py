"""Durable bounded goals and approval-gated execution plans."""
import json
from luna import core
from luna import jobs

ALLOWED_STEPS={"project_health":"Read-only local project health","github_status":"Read-only GitHub status","development_plan":"Prepare a development plan"}
MAX_STEPS=5

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS agent_goals (id INTEGER PRIMARY KEY, objective TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'proposed', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS agent_goal_steps (id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL, position INTEGER NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', job_id INTEGER, FOREIGN KEY(goal_id) REFERENCES agent_goals(id))""")

def propose_goal(objective, steps):
    if not isinstance(objective,str) or not 5<=len(objective.strip())<=500:
        raise ValueError("Invalid objective")
    if not isinstance(steps,list) or not 1<=len(steps)<=MAX_STEPS or any(s not in ALLOWED_STEPS for s in steps):
        raise ValueError("Steps must be bounded allowlisted actions")
    with core.connect() as db:
        _setup(db)
        now=core.timestamp()
        cur=db.execute("INSERT INTO agent_goals(objective,created_at,updated_at) VALUES(?,?,?)",(objective.strip(),now,now))
        goal_id=cur.lastrowid
        for i,kind in enumerate(steps):
            db.execute("INSERT INTO agent_goal_steps(goal_id,position,kind) VALUES(?,?,?)",(goal_id,i,kind))
    return goal_id

def list_goals(limit=30):
    with core.connect() as db:
        _setup(db)
        goals=db.execute("SELECT id,objective,state,created_at,updated_at FROM agent_goals ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        result=[]
        for id,objective,state,created,updated in goals:
            steps=db.execute("SELECT id,position,kind,state,job_id FROM agent_goal_steps WHERE goal_id=? ORDER BY position",(id,)).fetchall()
            result.append({"id":id,"objective":objective,"state":state,"created_at":created,"updated_at":updated,"steps":[dict(zip(("id","position","kind","state","job_id"),s)) for s in steps]})
    return result

def decide_goal(goal_id, approve):
    """Approval authorizes only explicitly listed low-risk actions."""
    with core.connect() as db:
        _setup(db)
        status="approved" if approve else "rejected"
        cur=db.execute("UPDATE agent_goals SET state=?,updated_at=? WHERE id=? AND state='proposed'",(status,core.timestamp(),goal_id))
        return cur.rowcount==1

def _goal(db, goal_id):
    row = db.execute(
        "SELECT id,objective,state,created_at,updated_at FROM agent_goals WHERE id=?",
        (goal_id,),
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
        "steps": [dict(zip(("id","position","kind","state","job_id"), x))
                  for x in steps],
    }


def goal_report(goal_id):
    """Explain progress and blockers from persisted records, never model guesses."""
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
                    "SELECT id,state,result,attempt_count,max_attempts FROM "
                    "work_items WHERE id=?", (step["job_id"],)
                ).fetchone()
                if row:
                    record = dict(zip(
                        ("id","state","result","attempt_count","max_attempts"), row
                    ))
            details.append({**step, "label": ALLOWED_STEPS[step["kind"]],
                            "job": record})
    done = sum(x["state"] == "completed" for x in details)
    return {
        "id": goal_id, "objective": goal["objective"], "state": goal["state"],
        "completed_steps": done, "total_steps": len(details),
        "next_step": next((x["position"] + 1 for x in details
                           if x["state"] != "completed"), None),
        "requires_attention": goal["state"] == "attention",
        "steps": details, "read_only": True,
    }


def control_goal(goal_id, action):
    """Pause or cancel future steps; never terminate a running operation."""
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
        if action == "pause" and state not in ("approved", "running"):
            return False
        if action == "resume" and state != "paused":
            return False
        if action == "cancel" and state not in (
            "proposed", "approved", "running", "paused", "attention"
        ):
            return False
        new_state = {
            "pause": "paused", "resume": "approved", "cancel": "cancelled"
        }[action]
        db.execute(
            "UPDATE agent_goals SET state=?,updated_at=? WHERE id=?",
            (new_state, core.timestamp(), goal_id),
        )
        if action == "cancel":
            for step in goal["steps"]:
                if step["state"] == "pending":
                    db.execute(
                        "UPDATE agent_goal_steps SET state='cancelled' WHERE id=?",
                        (step["id"],),
                    )
                elif step["state"] == "running" and step["job_id"] is not None:
                    # Only pending jobs can be cancelled; running handlers finish.
                    cur = db.execute(
                        "UPDATE work_items SET state='cancelled',next_attempt_at='',"
                        "updated_at=? WHERE id=? AND state IN ('queued','retry_wait')",
                        (core.timestamp(), step["job_id"]),
                    )
                    if cur.rowcount:
                        jobs._event(db, step["job_id"], "cancelled",
                                    "Owner cancelled goal")
                        db.execute(
                            "UPDATE agent_goal_steps SET state='cancelled' WHERE id=?",
                            (step["id"],),
                        )
        return True


def advance_goals():
    """Advance approved plans atomically, with no duplicates or unsafe replay.

    Goal and job writes share a single SQLite transaction. A pause blocks
    dispatch but completed work is reconciled after resume.
    """
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        jobs._setup(db)
        if not db.execute(
            "SELECT enabled FROM worker_config WHERE id=1"
        ).fetchone()[0]:
            return
        goal_ids = db.execute(
            "SELECT id FROM agent_goals WHERE state IN ('approved','running') "
            "ORDER BY id LIMIT 20"
        ).fetchall()
        for (goal_id,) in goal_ids:
            steps = db.execute(
                "SELECT id,kind,state,job_id FROM agent_goal_steps "
                "WHERE goal_id=? ORDER BY position", (goal_id,),
            ).fetchall()
            waiting = False
            failed = False
            for step_id, kind, state, job_id in steps:
                if state == "completed":
                    continue
                if state == "running":
                    row = db.execute(
                        "SELECT state FROM work_items WHERE id=?", (job_id,)
                    ).fetchone()
                    if row is None or row[0] in ("attention", "cancelled"):
                        db.execute(
                            "UPDATE agent_goal_steps SET state='attention' "
                            "WHERE id=?", (step_id,),
                        )
                        failed = True
                    elif row[0] == "completed":
                        db.execute(
                            "UPDATE agent_goal_steps SET state='completed' "
                            "WHERE id=?", (step_id,),
                        )
                        continue
                    else:
                        waiting = True
                    break
                if state in ("attention", "cancelled"):
                    failed = True
                    break
                if state == "pending":
                    if jobs._active_count(db) >= jobs.MAX_ACTIVE:
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
                                "Approved goal #" + str(goal_id), stamp)
                    db.execute(
                        "UPDATE agent_goal_steps SET state='running',job_id=? "
                        "WHERE id=?", (cur.lastrowid, step_id),
                    )
                    waiting = True
                    break
            new_state = ("attention" if failed else
                         "running" if waiting else "completed")
            db.execute(
                "UPDATE agent_goals SET state=?,updated_at=? WHERE id=?",
                (new_state, core.timestamp(), goal_id),
            )
