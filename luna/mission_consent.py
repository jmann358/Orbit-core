"""Explicit, short-lived owner authorization for ONE existing developer mission.

A conversational model's API key is not blanket developer permission. The
owner can approve at most two model attempts for one queued, allowlisted
mission. The grant is bound to the exact provider endpoint and model, expires
in one hour, never stores credentials, and never authorizes installing code.
"""
import os
import re
from datetime import datetime, timedelta, timezone

from luna.cloud_worker import connect
from luna.model_connection import classify_endpoint

MAX_CALLS = 2
EXPIRES_MINUTES = 60
MODEL_NAME = re.compile(r"[A-Za-z0-9._:-]{1,120}(?:/[A-Za-z0-9._:-]{1,120})?\Z")


def snapshot(environ=None):
    """Read-only, sanitized provider settings; never verify or expose the key."""
    from urllib.parse import urlsplit
    env = os.environ if environ is None else environ
    endpoint = (env.get("LUNA_MODEL_URL") or "").rstrip("/")
    model = (env.get("LUNA_MODEL_NAME") or "").strip()
    transport = classify_endpoint(endpoint)
    try:
        parts = urlsplit(endpoint)
        provider = parts.hostname or ""
        local_safe = (
            transport == "local"
            and parts.scheme == "http"
            and parts.port in (None, 11434, 1234)
            and not parts.username and not parts.password
            and not parts.query and not parts.fragment
        )
        cloud_safe = (
            transport == "cloud"
            and parts.scheme == "https"
            and parts.port in (None, 443)
            and not parts.username and not parts.password
            and not parts.query and not parts.fragment
        )
    except ValueError:
        return {"available": False, "provider": None, "model": None,
                "transport": None, "billing_possible": False}
    ready = bool(
        (cloud_safe or local_safe) and MODEL_NAME.fullmatch(model)
        and (transport == "local" or env.get("LUNA_API_KEY"))
    )
    return {
        "available": ready,
        "provider": provider if ready else None,
        "model": model if ready else None,
        "endpoint": endpoint if ready else None,
        "transport": transport if ready else None,
        "billing_possible": transport == "cloud" if ready else False,
    }


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS developer_mission_consents (
        mission_id INTEGER PRIMARY KEY,
        endpoint TEXT NOT NULL,
        model TEXT NOT NULL,
        approved_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_calls INTEGER NOT NULL DEFAULT 0,
        max_calls INTEGER NOT NULL DEFAULT 2,
        revoked INTEGER NOT NULL DEFAULT 0
    )""")


def _stamp(now=None):
    value = now or datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Time must be timezone aware")
    return value.astimezone(timezone.utc).isoformat()


def _mission(db, mission_id):
    if type(mission_id) is not int or mission_id < 1:
        return None
    return db.execute(
        "SELECT id,source,state,path,job_id FROM developer_missions WHERE id=?",
        (mission_id,),
    ).fetchone()


def authorize(db_path, mission_id, *, approved, now=None):
    """One separate, explicit owner action per mission, not a global setting."""
    if approved is not True:
        raise ValueError("Explicit affirmative authorization is required")
    snap = snapshot()
    if not snap["available"]:
        raise ValueError("A trusted configured model and any required API key are needed")
    stamp = _stamp(now)
    expires = (datetime.fromisoformat(stamp) +
               timedelta(minutes=EXPIRES_MINUTES)).isoformat()
    with connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        from luna.developer_agent import _setup as developer_setup
        developer_setup(db)
        _setup(db)
        mission = _mission(db, mission_id)
        if not mission or mission[1] != "owner" or mission[2] != "queued":
            raise ValueError("Only an owner's existing queued development mission may be authorized")
        paused = db.execute(
            "SELECT paused FROM developer_control WHERE id=1"
        ).fetchone()
        if not paused or paused[0]:
            raise ValueError("Development worker is paused or unavailable")
        if db.execute(
            "SELECT 1 FROM developer_mission_consents WHERE mission_id=?",
            (mission_id,),
        ).fetchone():
            raise ValueError("Already authorized once; no automatic renewal")
        db.execute(
            "INSERT INTO developer_mission_consents "
            "(mission_id,endpoint,model,approved_at,expires_at,max_calls) "
            "VALUES(?,?,?,?,?,?)",
            (mission_id, snap["endpoint"], snap["model"], stamp, expires, MAX_CALLS),
        )
    return {
        "mission_id": mission_id,
        "approved": True,
        "provider": snap["provider"],
        "model": snap["model"],
        "transport": snap["transport"],
        "may_incur_charges": snap["billing_possible"],
        "max_model_calls": MAX_CALLS,
        "expires_at": expires,
        "source_applied": False,
        "automatic_future_missions_authorized": False,
    }


def _eligible_db(db, mission_id, *, now=None, require_running=False):
    if type(mission_id) is not int or mission_id < 1:
        return False
    _setup(db)
    snap = snapshot()
    if not snap["available"]:
        return False
    record = db.execute(
        "SELECT m.source,m.state,m.job_id,c.endpoint,c.model,"
        "c.expires_at,c.used_calls,c.max_calls,c.revoked "
        "FROM developer_missions m JOIN developer_mission_consents c "
        "ON c.mission_id=m.id WHERE m.id=?", (mission_id,),
    ).fetchone()
    if not record:
        return False
    source, state, job_id, endpoint, model, expires, used, maximum, revoked = record
    if (source != "owner" or state not in (("working",) if require_running
                                           else ("queued","working"))
            or snap["endpoint"] != endpoint or snap["model"] != model
            or revoked or used >= maximum or maximum != MAX_CALLS
            or _stamp(now) >= expires):
        return False
    if require_running:
        row = db.execute(
            "SELECT status,kind,payload FROM cloud_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if row != ("running", "development_draft", str(mission_id)):
            return False
    return True


def eligible(db_path, mission_id):
    with connect(db_path) as db:
        return _eligible_db(db, mission_id)


def eligible_in_db(db, payload):
    """Use the *existing* claim transaction so queue ordering stays atomic."""
    if type(payload) is not str or not payload.isdecimal() or len(payload) > 10:
        return False
    return _eligible_db(db, int(payload))


def consume_for_request(db_path, mission_id):
    """Reserve a call before any network request; a crash cannot replay billing."""
    with connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        if not _eligible_db(db, mission_id, require_running=True):
            raise ValueError("Owner authorization expired, changed or was consumed")
        changed = db.execute(
            "UPDATE developer_mission_consents SET used_calls=used_calls+1 "
            "WHERE mission_id=? AND used_calls<max_calls AND revoked=0",
            (mission_id,),
        )
        if changed.rowcount != 1:
            raise ValueError("Owner model-call authorization has been exhausted")
    return True


def revoke(db_path, mission_id):
    with connect(db_path) as db:
        _setup(db)
        cur = db.execute(
            "UPDATE developer_mission_consents SET revoked=1 "
            "WHERE mission_id=? AND revoked=0 AND used_calls=0",
            (mission_id,),
        )
        if cur.rowcount != 1:
            raise ValueError("Only an unused, active authorization can be revoked")
    return {"mission_id": mission_id, "revoked": True}


def info(db_path, mission_id):
    snap = snapshot()
    with connect(db_path) as db:
        _setup(db)
        record = db.execute(
            "SELECT endpoint,model,approved_at,expires_at,used_calls,max_calls,revoked "
            "FROM developer_mission_consents WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
    if record is None:
        return {"mission_id": mission_id, "recorded": False,
                "ready_unverified": snap["available"],
                "provider": snap["provider"], "model": snap["model"],
                "may_incur_charges": snap["billing_possible"],
                "max_model_calls": MAX_CALLS}
    endpoint, model, approved, expires, used, maximum, revoked = record
    return {
        "mission_id": mission_id, "recorded": True,
        "ready_unverified": snap["available"] and snap["endpoint"] == endpoint
                             and snap["model"] == model and not revoked
                             and used < maximum and _stamp() < expires,
        "provider": snap["provider"] if snap["endpoint"] == endpoint else None,
        "model": model, "may_incur_charges": classify_endpoint(endpoint) == "cloud",
        "approved_at": approved, "expires_at": expires, "used_calls": used,
        "max_model_calls": maximum, "revoked": bool(revoked),
        "credentials_stored": False,
    }
