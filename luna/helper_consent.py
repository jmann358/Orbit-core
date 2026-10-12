"""One-click, single-task AI consent for existing approved Luna helpers.

An agent's creation approval does NOT authorize paid cloud model calls.
One helper task may consume one model call using the owner's already configured
chat provider, with no secret stored and no permission for future tasks.
"""
from datetime import datetime, timedelta, timezone

from luna import core
from luna.mission_consent import snapshot

EXPIRES_MINUTES = 60


def _now(now=None):
    instant = now or datetime.now(timezone.utc)
    return instant.astimezone(timezone.utc).isoformat()


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS helper_task_consents (
        task_id INTEGER PRIMARY KEY,
        endpoint TEXT NOT NULL,
        model TEXT NOT NULL,
        approved_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0,
        revoked INTEGER NOT NULL DEFAULT 0
    )""")


def provider():
    settings = snapshot()
    return {
        "available_unverified": settings["available"],
        "provider": settings["provider"], "model": settings["model"],
        "transport": settings["transport"],
        "may_incur_charges": settings["billing_possible"],
        "max_calls_per_approval": 1,
        "expires_minutes": EXPIRES_MINUTES,
    }


def authorize(task_id, approve, *, now=None):
    """Create one bounded authorization, only for an active helper's queued AI task."""
    if approve is not True:
        raise ValueError("Explicit owner approval is required.")
    if type(task_id) is not int or task_id < 1:
        raise ValueError("Unknown helper task.")
    config = snapshot()
    if not config["available"]:
        raise ValueError("A permitted AI model must be configured for Luna chat first.")
    from luna import custom_agents
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        custom_agents._setup(db)
        _setup(db)
        row = db.execute(
            "SELECT t.kind,t.status,a.status,a.template FROM custom_agent_tasks t "
            "JOIN custom_agents a ON a.id=t.agent_id WHERE t.id=?", (task_id,)
        ).fetchone()
        if (not row or row[0] not in custom_agents.MODEL_TASKS
                or row[1] != "queued" or row[2] != "active"
                or row[0] not in custom_agents.TEMPLATES[row[3]]["capabilities"]):
            raise ValueError("Only queued model tasks for active approved helpers can be authorized.")
        if db.execute("SELECT 1 FROM helper_task_consents WHERE task_id=?",
                      (task_id,)).fetchone():
            raise ValueError("This task already had an authorization; no automatic renewal.")
        created = datetime.fromisoformat(_now(now))
        db.execute(
            "INSERT INTO helper_task_consents(task_id,endpoint,model,approved_at,expires_at) "
            "VALUES(?,?,?,?,?)", (task_id, config["endpoint"], config["model"],
                                   created.isoformat(),
                                   (created + timedelta(minutes=EXPIRES_MINUTES)).isoformat())
        )
    return {"task_id": task_id, "approved": True, "provider": config["provider"],
            "model": config["model"], "may_incur_charges": config["billing_possible"],
            "model_calls": 1, "expires_minutes": EXPIRES_MINUTES,
            "future_tasks_authorized": False, "code_applied": False}


def _eligible(db, task_id, *, require_used=False):
    if type(task_id) is not int or task_id < 1:
        return False
    _setup(db)
    config = snapshot()
    if not config["available"]:
        return False
    row = db.execute(
        "SELECT c.endpoint,c.model,c.expires_at,c.used,c.revoked,"
        "t.status,t.kind,a.status FROM helper_task_consents c "
        "JOIN custom_agent_tasks t ON t.id=c.task_id "
        "JOIN custom_agents a ON a.id=t.agent_id WHERE c.task_id=?",
        (task_id,),
    ).fetchone()
    if not row:
        return False
    endpoint, model, expiry, used, revoked, task_state, kind, agent_state = row
    return bool(
        not revoked and endpoint == config["endpoint"] and model == config["model"]
        and expiry > _now() and agent_state == "active"
        and kind in ("code_review", "plan")
        and task_state == ("running" if require_used else "queued")
        and bool(used) == require_used
    )


def eligible_in_db(db, task_id):
    """Caller owns SQLite claim transaction. Never writes or calls a provider."""
    return _eligible(db, task_id)


def consume_in_db(db, task_id):
    if not _eligible(db, task_id):
        raise ValueError("Helper's one-task permission is unavailable")
    result = db.execute(
        "UPDATE helper_task_consents SET used=1 "
        "WHERE task_id=? AND used=0 AND revoked=0", (task_id,)
    )
    if result.rowcount != 1:
        raise ValueError("Helper approval was consumed")


def permitted_running(task_id):
    """Use before making a model request; claim has already consumed approval."""
    with core.connect() as db:
        return _eligible(db, task_id, require_used=True)


def approved_task_ids():
    with core.connect() as db:
        _setup(db)
        return [row[0] for row in db.execute(
            "SELECT task_id FROM helper_task_consents WHERE revoked=0 ORDER BY task_id"
        ).fetchall()]


def revoke(task_id):
    with core.connect() as db:
        _setup(db)
        result = db.execute(
            "UPDATE helper_task_consents SET revoked=1 "
            "WHERE task_id=? AND used=0 AND revoked=0", (task_id,)
        )
        if result.rowcount != 1:
            raise ValueError("Only an unused helper authorization may be revoked.")
    return {"task_id": task_id, "revoked": True}
