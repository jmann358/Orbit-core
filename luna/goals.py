"""Durable bounded goals and approval-gated execution plans."""
import json
from luna import core
from luna.jobs import create_job, list_jobs

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

def advance_goals():
    """Queue at most one step per approved goal, reconcile completed jobs, never replay interrupted jobs."""
    jobs={j["id"]:j for j in list_jobs(limit=500)}
    with core.connect() as db:
        _setup(db)
        goals=db.execute("SELECT id FROM agent_goals WHERE state IN ('approved','running') ORDER BY id LIMIT 20").fetchall()
        for (goal_id,) in goals:
            steps=db.execute("SELECT id,kind,state,job_id FROM agent_goal_steps WHERE goal_id=? ORDER BY position",(goal_id,)).fetchall()
            waiting=False
            failed=False
            for step_id,kind,state,job_id in steps:
                if state=="completed":
                    continue
                if state=="running":
                    job=jobs.get(job_id)
                    if job is None or job["state"] in ("attention","cancelled"):
                        db.execute("UPDATE agent_goal_steps SET state='attention' WHERE id=?",(step_id,))
                        failed=True
                    elif job["state"]=="completed":
                        db.execute("UPDATE agent_goal_steps SET state='completed' WHERE id=?",(step_id,))
                        continue
                    else:
                        waiting=True
                    break
                if state=="attention":
                    failed=True
                    break
                if state=="pending":
                    # Release the current SQLite read transaction before the job queue writes.
                    # The single goal worker is responsible for step ordering.
                    db.commit()
                    job_id=create_job(kind,"Goal "+str(goal_id)+": "+ALLOWED_STEPS[kind])
                    db.execute("UPDATE agent_goal_steps SET state='running',job_id=? WHERE id=?",(job_id,step_id))
                    waiting=True
                    break
            new_state="attention" if failed else "running" if waiting else "completed"
            db.execute("UPDATE agent_goals SET state=?,updated_at=? WHERE id=?",(new_state,core.timestamp(),goal_id))
