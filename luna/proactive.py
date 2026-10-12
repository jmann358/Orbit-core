"""Preview bounded helpful actions based on local persisted state.

No timers, push notifications, surveillance, model calls or auto-action.
An owner must explicitly request any resulting local review item.
"""
from luna import core, jobs
from luna import goals
from luna.requests import create_request

MAX_SUGGESTIONS = 2


def preview():
    with core.connect() as db:
        goals._setup(db)
        jobs._setup(db)
        attention = db.execute(
            "SELECT COUNT(*) FROM agent_goals WHERE state='attention'"
        ).fetchone()[0]
        unresolved = db.execute(
            "SELECT COUNT(*) FROM work_items WHERE state='attention'"
        ).fetchone()[0]
        pending = db.execute(
            "SELECT COUNT(*) FROM agent_goals WHERE state='proposed'"
        ).fetchone()[0]
    recommendations = []
    if attention:
        recommendations.append({
            "id": "goals_needing_review",
            "title": "Review blocked goals",
            "explanation": str(attention) +
                           " approved goals are stopped for owner review.",
            "action": "Open Goals and inspect audit history",
            "priority": "high",
        })
    if unresolved:
        recommendations.append({
            "id": "jobs_needing_review",
            "title": "Investigate failed tasks",
            "explanation": str(unresolved) + " tasks need inspection.",
            "action": "Review job results before retrying anything",
            "priority": "medium",
        })
    if pending:
        recommendations.append({
            "id": "pending_goal_approvals",
            "title": "Review proposed work",
            "explanation": str(pending) + " goals await an explicit decision.",
            "action": "Inspect each plan before approval",
            "priority": "low",
        })
    return {
        "suggestions": recommendations[:MAX_SUGGESTIONS],
        "requires_user_action": True,
        "automatic_notifications_enabled": False,
        "auto_execute": False,
        "read_only": True,
    }


def save_review_request(suggestion_id):
    if type(suggestion_id) is not str:
        raise ValueError("Invalid suggestion")
    eligible = {s["id"]: s for s in preview()["suggestions"]}
    if suggestion_id not in eligible:
        raise ValueError("Suggestion is not currently applicable")
    selected = eligible[suggestion_id]
    return create_request(
        "information", selected["priority"], selected["title"],
        selected["explanation"] + " " + selected["action"] +
        ". This is a manual, non-executing reminder.",
        "Local ORBIT review suggestion: " + suggestion_id,
    )
