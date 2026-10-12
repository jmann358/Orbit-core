"""Deterministic specialist handoffs over persisted approved goal outcomes.

No AI processes, new tools, mutable agent prompts, or network calls. This
read-only representation lets future independently approved agents consume
traceable facts, not arbitrary directives.
"""
from luna import core, jobs, goals, agent_registry

MAX_RESULT = 900


def bundle(goal_id, step_position):
    if type(goal_id) is not int or goal_id < 1:
        raise ValueError("Invalid goal id")
    if type(step_position) is not int or step_position < 0 or step_position >= goals.MAX_STEPS:
        raise ValueError("Invalid step position")
    with core.connect() as db:
        goals._setup(db)
        jobs._setup(db)
        record = goals._goal(db, goal_id)
        if record is None:
            return None
        steps = record["steps"]
        target = next((step for step in steps
                       if step["position"] == step_position), None)
        if target is None:
            return None
        try:
            assignee = agent_registry.specialist_for(target["kind"])
        except ValueError:
            assignee = None
        outcomes = []
        ready = bool(assignee and record["state"] in (
            "approved", "running", "completed"))
        for step in steps:
            if step["position"] >= step_position:
                break
            result = None
            if step["job_id"] is not None:
                result = db.execute(
                    "SELECT id,kind,state,result FROM work_items WHERE id=?",
                    (step["job_id"],),
                ).fetchone()
            if (step["state"] != "completed" or result is None
                    or result[1] != step["kind"] or result[2] != "completed"):
                ready = False
                continue
            try:
                source = agent_registry.specialist_for(step["kind"])
            except ValueError:
                ready = False
                continue
            outcomes.append({
                "step": step["position"], "job_id": result[0],
                "specialist": source, "kind": step["kind"],
                "outcome": result[3][:MAX_RESULT],
                "source": "persisted_completed_work_item",
                "trusted_as_instruction": False,
            })
    return {
        "goal_id": goal_id, "step": step_position,
        "assigned_specialist": assignee, "ready": ready,
        "outcomes": outcomes, "read_only": True,
        "handoff_is_authorization": False, "executes": False,
        "next_action": "Existing worker still enforces separate approved step",
    }
