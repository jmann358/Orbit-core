"""Persistent human-mediated Luna requests. Never contacts external services."""
from datetime import datetime, timezone
from luna import core

PRIORITIES = ("high", "medium", "low")
KINDS = ("decision", "technical_help", "permission", "information", "issue")
_PRIORITY_RANK={"high":0,"medium":1,"low":2}

def _now():
    return datetime.now(timezone.utc).isoformat()

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS luna_requests (
      id INTEGER PRIMARY KEY, kind TEXT NOT NULL, priority TEXT NOT NULL,
      title TEXT NOT NULL, message TEXT NOT NULL, context TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
      resolved_at TEXT)""")
    columns={row[1] for row in db.execute("PRAGMA table_info(luna_requests)").fetchall()}
    if "repeat_count" not in columns:
        db.execute("ALTER TABLE luna_requests ADD COLUMN repeat_count INTEGER NOT NULL DEFAULT 1")
    if "last_seen_at" not in columns:
        db.execute("ALTER TABLE luna_requests ADD COLUMN last_seen_at TEXT NOT NULL DEFAULT ''")
        db.execute("UPDATE luna_requests SET last_seen_at=created_at WHERE last_seen_at=''")

def create_request(kind, priority, title, message, context=""):
    if kind not in KINDS or priority not in PRIORITIES:
        raise ValueError("Invalid request type or priority")
    if not isinstance(title,str) or not 3 <= len(title.strip()) <= 120:
        raise ValueError("Title must be 3-120 characters")
    if not isinstance(message,str) or not 5 <= len(message.strip()) <= 3000:
        raise ValueError("Message must be 5-3000 characters")
    if not isinstance(context,str) or len(context)>3000:
        raise ValueError("Context is too long")
    title=title.strip()
    now=_now()
    with core.connect() as db:
        _setup(db)
        existing=db.execute(
            """SELECT id,priority,repeat_count FROM luna_requests
               WHERE kind=? AND title=? AND status='open' LIMIT 1""",
            (kind,title)).fetchone()
        if existing:
            request_id,current_priority,repeat_count=existing
            effective=(priority if _PRIORITY_RANK[priority]<_PRIORITY_RANK[current_priority]
                       else current_priority)
            db.execute("""UPDATE luna_requests
                          SET repeat_count=repeat_count+1,last_seen_at=?,priority=?
                          WHERE id=? AND status='open'""",
                       (now,effective,request_id))
            return {"id":request_id,"created":False,
                    "repeat_count":repeat_count+1,"priority":effective}
        cur=db.execute("""INSERT INTO luna_requests
          (kind,priority,title,message,context,created_at,last_seen_at)
          VALUES(?,?,?,?,?,?,?)""",
          (kind,priority,title,message.strip(),context.strip(),now,now))
        return {"id":cur.lastrowid,"created":True,"repeat_count":1,"priority":priority}

def list_requests(limit=100, open_only=False):
    with core.connect() as db:
        _setup(db)
        where="WHERE status='open'" if open_only else ""
        rows=db.execute(f"""SELECT id,kind,priority,title,message,context,status,
          created_at,repeat_count,last_seen_at FROM luna_requests {where}
          ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
          last_seen_at DESC,id DESC LIMIT ?""",(min(max(int(limit),1),100),)).fetchall()
    keys=("id","kind","priority","title","message","context","status",
          "created_at","repeat_count","last_seen_at")
    return [dict(zip(keys,row)) for row in rows]

def decide_request(request_id, decision):
    if decision not in ("acknowledged","dismissed"):
        return False
    with core.connect() as db:
        _setup(db)
        cur=db.execute("""UPDATE luna_requests SET status=?,resolved_at=?
          WHERE id=? AND status='open'""",
          (decision,_now(),request_id))
        return cur.rowcount==1

def relay_text(request):
    """A portable message for the user to copy to another assistant."""
    recurrence=("\nRepeated detections: "+str(request["repeat_count"])
                if request.get("repeat_count",1)>1 else "")
    return ("Luna's ORBIT development request #"+str(request["id"])+
            "\nPriority: "+request["priority"]+"\nType: "+request["kind"]+
            "\nSubject: "+request["title"]+"\nRequest: "+request["message"]+
            ("\nContext: "+request["context"] if request["context"] else "")+
            recurrence+
            "\nPlease advise on a safe implementation. Do not assume changes were applied.")
