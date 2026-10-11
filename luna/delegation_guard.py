"""Runtime check for jobs linked to approved specialist goal steps.

A pause defers queued jobs. A missing/invalid approval, changed job kind,
or reordered step is denied and quarantined for review. Existing standalone
allowlisted maintenance jobs are intentionally outside goal delegation.
"""
from luna import agent_registry


def authorize_claim(db, job_id, kind):
    """Return (allow|defer|deny, reason, goal_id, step_id).

    Caller must hold BEGIN IMMEDIATE and perform the job state transition in
    that same transaction. No external calls or model-generated instructions.
    """
    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='agent_goal_steps'"
    ).fetchone():
        return "allow", "standalone task", None, None
    rows = db.execute(
        """SELECT s.id,s.goal_id,s.kind,s.state,s.position,g.state
           FROM agent_goal_steps s
           LEFT JOIN agent_goals g ON g.id=s.goal_id
           WHERE s.job_id=? LIMIT 2""", (job_id,),
    ).fetchall()
    if not rows:
        return "allow", "standalone task", None, None
    if len(rows) != 1:
        return "deny", "Multiple steps reference one job", None, None
    step_id, goal_id, assigned_kind, step_state, position, goal_state = rows[0]
    if goal_state == "paused":
        return "defer", "Owner paused this goal", goal_id, step_id
    if goal_state not in ("approved", "running"):
        return "deny", "Goal has no active approval", goal_id, step_id
    if assigned_kind != kind or step_state != "running":
        return "deny", "Task differs from approved step", goal_id, step_id
    try:
        agent_registry.specialist_for(kind)
    except ValueError:
        return "deny", "Specialist capability missing", goal_id, step_id
    incomplete = db.execute(
        "SELECT 1 FROM agent_goal_steps WHERE goal_id=? AND position<? "
        "AND state!='completed' LIMIT 1", (goal_id, position),
    ).fetchone()
    if incomplete:
        return "deny", "Prior dependency is unfinished", goal_id, step_id
    return "allow", "approved specialist goal", goal_id, step_id
