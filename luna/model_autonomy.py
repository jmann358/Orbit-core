"""Budget gate for unattended Luna model drafting.

Automatic model use is disabled by default and is local-endpoint-only. Cloud endpoints
are never eligible for unattended calls through this gate.
"""
import os
from datetime import datetime, timezone
from urllib.parse import urlparse
from luna import core

LOCAL_HOSTS=frozenset({"localhost","127.0.0.1"})

def _today():
    return datetime.now(timezone.utc).date().isoformat()

def endpoint_class():
    endpoint=os.environ.get("LUNA_MODEL_URL","").rstrip("/")
    if not endpoint:
        return "unconfigured"
    parsed=urlparse(endpoint)
    if (parsed.scheme=="http" and parsed.hostname in LOCAL_HOSTS
            and parsed.username is None and parsed.password is None):
        return "local"
    if parsed.scheme=="https":
        return "cloud"
    return "blocked"

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS model_autonomy_config (
      id INTEGER PRIMARY KEY CHECK(id=1),
      enabled INTEGER NOT NULL DEFAULT 0,
      max_daily_calls INTEGER NOT NULL DEFAULT 0,
      approved_by TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL DEFAULT '')""")
    db.execute("""INSERT OR IGNORE INTO model_autonomy_config(
      id,enabled,max_daily_calls,approved_by,updated_at) VALUES(1,0,0,'','')""")
    db.execute("""CREATE TABLE IF NOT EXISTS model_autonomy_usage (
      day TEXT PRIMARY KEY, calls INTEGER NOT NULL DEFAULT 0)""")

def status():
    with core.connect() as db:
        _setup(db)
        enabled,max_calls,approved_by=db.execute(
            "SELECT enabled,max_daily_calls,approved_by FROM model_autonomy_config WHERE id=1"
        ).fetchone()
        row=db.execute("SELECT calls FROM model_autonomy_usage WHERE day=?",(_today(),)).fetchone()
    used=row[0] if row else 0
    endpoint=endpoint_class()
    return {
        "enabled":bool(enabled),
        "max_daily_calls":max_calls,
        "calls_today":used,
        "remaining_today":max(0,max_calls-used),
        "endpoint_class":endpoint,
        "local_only":True,
        "automatic_cloud_calls":False,
        "eligible":bool(enabled) and approved_by=="owner" and endpoint=="local" and used<max_calls,
    }

def configure_local(enabled,max_daily_calls,approved_by):
    if approved_by!="owner":
        raise ValueError("Owner authorization required")
    if type(enabled) is not bool:
        raise ValueError("Enabled must be boolean")
    if type(max_daily_calls) is not int or not 0<=max_daily_calls<=10:
        raise ValueError("Daily call limit must be between 0 and 10")
    if enabled and max_daily_calls<1:
        raise ValueError("Enabled automatic drafting needs a positive daily limit")
    now=datetime.now(timezone.utc).isoformat()
    with core.connect() as db:
        _setup(db)
        db.execute("""UPDATE model_autonomy_config
                      SET enabled=?,max_daily_calls=?,approved_by=?,updated_at=?
                      WHERE id=1""",
                   (int(enabled),max_daily_calls,approved_by,now))
    return status()

def reserve_call():
    """Atomically reserve one unattended LOCAL model call, or fail closed."""
    if endpoint_class()!="local":
        return {"allowed":False,"reason":"local_model_required"}
    with core.connect() as db:
        _setup(db)
        enabled,max_calls,approved_by=db.execute(
            "SELECT enabled,max_daily_calls,approved_by FROM model_autonomy_config WHERE id=1"
        ).fetchone()
        if not enabled or approved_by!="owner":
            return {"allowed":False,"reason":"disabled"}
        day=_today()
        row=db.execute("SELECT calls FROM model_autonomy_usage WHERE day=?",(day,)).fetchone()
        used=row[0] if row else 0
        if used>=max_calls:
            return {"allowed":False,"reason":"daily_limit"}
        if row:
            db.execute("UPDATE model_autonomy_usage SET calls=calls+1 WHERE day=?",(day,))
        else:
            db.execute("INSERT INTO model_autonomy_usage(day,calls) VALUES(?,1)",(day,))
    return {"allowed":True,"reason":"local_budget","remaining_today":max_calls-used-1}
