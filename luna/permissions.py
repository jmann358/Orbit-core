"""Permission registry: conservative reviewable capabilities, no self-grant."""
from datetime import datetime, timezone, timedelta
from luna import core

CAPABILITIES = {
 "read_diagnostics": {"tier":1,"auto":True,"daily_limit":48},
 "prepare_patch": {"tier":2,"auto":False,"daily_limit":10},
 "run_tests": {"tier":2,"auto":False,"daily_limit":12},
 "apply_code": {"tier":3,"auto":False,"daily_limit":0},
 "security_change": {"tier":3,"auto":False,"daily_limit":0},
 "spend_money": {"tier":3,"auto":False,"daily_limit":0},
}
def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS capability_grants (
      id INTEGER PRIMARY KEY, capability TEXT NOT NULL, expires_at TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active', approved_by TEXT NOT NULL,
      created_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS capability_usage (
      capability TEXT NOT NULL, day TEXT NOT NULL, used INTEGER NOT NULL,
      PRIMARY KEY(capability,day))""")

def policy():
    return {"capabilities":[{"name":k,**v} for k,v in CAPABILITIES.items()],
            "automatic_expansion":False,"model_can_grant":False}

def request_grant(capability):
    """Produce request data, not an active grant."""
    if capability not in CAPABILITIES:
        raise ValueError("Unknown capability")
    return {"capability":capability,"requires_owner_approval":True,
            "granted":False,"daily_limit":CAPABILITIES[capability]["daily_limit"]}

def grant(capability, minutes, approved_by):
    """Explicit owner-side approval hook; never called by Luna's worker."""
    if capability not in ("prepare_patch","run_tests"):
        raise ValueError("Capability cannot be temporarily delegated")
    if type(minutes) is not int or not 1<=minutes<=120:
        raise ValueError("Grant duration must be 1-120 minutes")
    if approved_by!="owner":
        raise ValueError("Owner authorization required")
    now=datetime.now(timezone.utc)
    with core.connect() as db:
        _setup(db)
        cur=db.execute("""INSERT INTO capability_grants
          (capability,expires_at,approved_by,created_at) VALUES(?,?,?,?)""",
          (capability,(now+timedelta(minutes=minutes)).isoformat(),approved_by,now.isoformat()))
        return cur.lastrowid

def revoke(grant_id):
    with core.connect() as db:
        _setup(db)
        cur=db.execute("UPDATE capability_grants SET status='revoked' WHERE id=? AND status='active'",(grant_id,))
        return cur.rowcount==1

def check(capability, now=None):
    if capability not in CAPABILITIES:
        return False
    if CAPABILITIES[capability]["auto"]:
        return True
    now=now or datetime.now(timezone.utc)
    with core.connect() as db:
        _setup(db)
        row=db.execute("""SELECT 1 FROM capability_grants WHERE capability=?
          AND status='active' AND expires_at>? LIMIT 1""",(capability,now.isoformat())).fetchone()
    return bool(row)

def consume(capability, now=None):
    """Atomically count a bounded operation. Call before a permitted action."""
    if capability not in CAPABILITIES or not check(capability,now):
        return False
    cap=CAPABILITIES[capability]["daily_limit"]
    if cap==0:
        return False
    day=(now or datetime.now(timezone.utc)).date().isoformat()
    with core.connect() as db:
        _setup(db)
        db.execute("INSERT OR IGNORE INTO capability_usage(capability,day,used) VALUES(?,?,0)",(capability,day))
        result=db.execute("""UPDATE capability_usage SET used=used+1
          WHERE capability=? AND day=? AND used<?""",(capability,day,cap))
        return result.rowcount==1
