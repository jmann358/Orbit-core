"""Persistent human-mediated Luna requests. Never contacts external services."""
from datetime import datetime, timezone
from luna import core

PRIORITIES = ("high", "medium", "low")
KINDS = ("decision", "technical_help", "permission", "information", "issue")

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS luna_requests (
      id INTEGER PRIMARY KEY, kind TEXT NOT NULL, priority TEXT NOT NULL,
      title TEXT NOT NULL, message TEXT NOT NULL, context TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
      resolved_at TEXT)""")

def create_request(kind, priority, title, message, context="", *, dedupe_context=False):
    """Create a local request, optionally reusing exact evidence in any status.

    Evidence delivery uses kind, title and the complete bounded context as its
    identity. A resolved matching request still proves that evidence arrived.
    Other callers retain the existing kind/title/open-request deduplication.
    """
    if kind not in KINDS or priority not in PRIORITIES:
        raise ValueError("Invalid request type or priority")
    if not isinstance(title,str) or not 3 <= len(title.strip()) <= 120:
        raise ValueError("Title must be 3-120 characters")
    if not isinstance(message,str) or not 5 <= len(message.strip()) <= 3000:
        raise ValueError("Message must be 5-3000 characters")
    if not isinstance(context,str) or len(context)>3000:
        raise ValueError("Context is too long")
    if type(dedupe_context) is not bool:
        raise ValueError("Invalid context deduplication option")
    with core.connect() as db:
        if dedupe_context:
            # Serialize evidence lookup and insert across worker connections.
            db.execute("BEGIN IMMEDIATE")
        _setup(db)
        if dedupe_context:
            existing=db.execute(
                "SELECT id FROM luna_requests WHERE kind=? AND title=? "
                "AND context=? ORDER BY id LIMIT 1",
                (kind,title.strip(),context.strip())).fetchone()
        else:
            # Prevent repeated identical open requests.
            existing=db.execute(
                "SELECT id FROM luna_requests WHERE kind=? AND title=? AND status='open' LIMIT 1",
                (kind,title.strip())).fetchone()
        if existing:
            return {"id":existing[0],"created":False}
        cur=db.execute("""INSERT INTO luna_requests
          (kind,priority,title,message,context,created_at) VALUES(?,?,?,?,?,?)""",
          (kind,priority,title.strip(),message.strip(),context.strip(),
           datetime.now(timezone.utc).isoformat()))
        return {"id":cur.lastrowid,"created":True}

def list_requests(limit=100, open_only=False):
    with core.connect() as db:
        _setup(db)
        where="WHERE status='open'" if open_only else ""
        rows=db.execute(f"""SELECT id,kind,priority,title,message,context,status,created_at
          FROM luna_requests {where} ORDER BY CASE priority WHEN 'high' THEN 0
          WHEN 'medium' THEN 1 ELSE 2 END,id DESC LIMIT ?""",(min(max(int(limit),1),100),)).fetchall()
    return [dict(zip(("id","kind","priority","title","message","context","status","created_at"),row)) for row in rows]

def decide_request(request_id, decision):
    if decision not in ("acknowledged","dismissed"):
        return False
    with core.connect() as db:
        _setup(db)
        cur=db.execute("""UPDATE luna_requests SET status=?,resolved_at=?
          WHERE id=? AND status='open'""",
          (decision,datetime.now(timezone.utc).isoformat(),request_id))
        return cur.rowcount==1

def relay_text(request):
    """A portable message for the user to copy to another assistant."""
    return ("Luna's ORBIT development request #"+str(request["id"])+
            "\\nPriority: "+request["priority"]+"\\nType: "+request["kind"]+
            "\\nSubject: "+request["title"]+"\\nRequest: "+request["message"]+
            ("\\nContext: "+request["context"] if request["context"] else "")+
            "\\nPlease advise on a safe implementation. Do not assume changes were applied.")
