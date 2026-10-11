"""One local, deduplicated owner request per blocked goal.

Runs from the existing local worker only. No notifications, external calls,
model inference or background service is added.
"""
from luna import core, goals
from luna.requests import create_request

MAX_PER_TICK = 5


def tick():
    """Surface newly blocked goals as owner-reviewed local requests.

    An event records successful escalation. Repeated worker ticks do not
    create new requests after acknowledgement or dismissal.
    """
    with core.connect() as db:
        goals._setup(db)
        rows = db.execute(
            """SELECT g.id,g.objective FROM agent_goals g
               WHERE g.state='attention' AND NOT EXISTS (
                 SELECT 1 FROM agent_goal_events e
                 WHERE e.goal_id=g.id AND e.event='owner_notified')
               ORDER BY g.id LIMIT ?""", (MAX_PER_TICK,),
        ).fetchall()
    created = []
    for goal_id, objective in rows:
        outcome = create_request(
            "decision", "medium", "Goal #" + str(goal_id) + " needs review",
            "An approved ORBIT goal stopped because a step failed, was "
            "interrupted or could not be authorized. Review its goal report "
            "and the linked task's event log. No step was replayed and no "
            "new permissions were granted. A fresh plan requires approval.",
            "Goal #" + str(goal_id) + ": " + objective[:350],
        )
        with core.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            goals._setup(db)
            # Do not record on a recovered goal or duplicate an event.
            status = db.execute(
                "SELECT state FROM agent_goals WHERE id=?", (goal_id,)
            ).fetchone()
            if status and status[0] == "attention" and not db.execute(
                "SELECT 1 FROM agent_goal_events WHERE goal_id=? "
                "AND event='owner_notified'", (goal_id,),
            ).fetchone():
                goals._event(db, goal_id, "owner_notified",
                             "Local review request #" + str(outcome["id"]))
                created.append(goal_id)
    return created
