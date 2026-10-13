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
    binding = db.execute(
        "SELECT goal_id,goal_revision,goal_plan_digest,max_attempts FROM work_items WHERE id=?", (job_id,)
    ).fetchone()
    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='agent_goal_steps'"
    ).fetchone():
        return (("deny", "Bound mission is missing", None, None)
                if binding and binding[0] is not None else ("allow", "standalone task", None, None))
    from luna import goals
    goals._setup(db)
    rows = db.execute(
        """SELECT s.id,s.goal_id,s.kind,s.state,s.position,g.state
           FROM agent_goal_steps s
           LEFT JOIN agent_goals g ON g.id=s.goal_id
           WHERE s.job_id=? LIMIT 2""", (job_id,),
    ).fetchall()
    if not rows:
        return (("deny", "Bound mission step is missing", binding[0], None)
                if binding and binding[0] is not None else ("allow", "standalone task", None, None))
    if len(rows) != 1:
        return "deny", "Multiple steps reference one job", None, None
    step_id, goal_id, assigned_kind, step_state, position, goal_state = rows[0]
    if goal_state == "paused":
        return "defer", "Owner paused this goal", goal_id, step_id
    if goal_state not in ("approved", "running"):
        return "deny", "Goal has no active approval", goal_id, step_id
    if not goals.plan_integrity(db, goal_id, approved=True):
        return "deny", "Approved plan revision changed", goal_id, step_id
    revision, digest = db.execute(
        "SELECT revision,approval_digest FROM agent_goals WHERE id=?", (goal_id,)
    ).fetchone()
    if binding != (goal_id, revision, digest, goals.jobs._attempt_limit(kind)):
        return "deny", "Job is not bound to the approved mission revision", goal_id, step_id
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
