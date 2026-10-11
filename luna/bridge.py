"""Auditable, user-mediated Luna ↔ ChatGPT bridge. No outbound calls."""
from datetime import datetime, timezone
from luna import core

STATES = ("awaiting_relay", "awaiting_reply", "replied", "closed")
PRIORITIES = ("high", "medium", "low")

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS bridge_threads (
      id INTEGER PRIMARY KEY, title TEXT NOT NULL, priority TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'awaiting_relay', created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS bridge_messages (
      id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL,
      sender TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY(thread_id) REFERENCES bridge_threads(id))""")

def _now():
    return datetime.now(timezone.utc).isoformat()

def create_thread(title, priority, message):
    if priority not in PRIORITIES or not isinstance(title,str) or not 3<=len(title.strip())<=120:
        raise ValueError("Invalid bridge title or priority")
    if not isinstance(message,str) or not 5<=len(message.strip())<=6000:
        raise ValueError("Invalid bridge message")
    with core.connect() as db:
        _setup(db)
        now=_now()
        cur=db.execute("INSERT INTO bridge_threads(title,priority,created_at,updated_at) VALUES(?,?,?,?)",
                       (title.strip(),priority,now,now))
        thread_id=cur.lastrowid
        db.execute("INSERT INTO bridge_messages(thread_id,sender,content,created_at) VALUES(?,'luna',?,?)",
                   (thread_id,message.strip(),now))
        return thread_id

def list_threads(limit=50):
    with core.connect() as db:
        _setup(db)
        rows=db.execute("""SELECT id,title,priority,status,created_at,updated_at
          FROM bridge_threads ORDER BY CASE priority WHEN 'high' THEN 0
          WHEN 'medium' THEN 1 ELSE 2 END,id DESC LIMIT ?""",(min(max(int(limit),1),100),)).fetchall()
    return [dict(zip(("id","title","priority","status","created_at","updated_at"),row)) for row in rows]

def get_thread(thread_id):
    with core.connect() as db:
        _setup(db)
        row=db.execute("SELECT id,title,priority,status,created_at,updated_at FROM bridge_threads WHERE id=?",(thread_id,)).fetchone()
        if not row:
            return None
        messages=db.execute("SELECT id,sender,content,created_at FROM bridge_messages WHERE thread_id=? ORDER BY id",(thread_id,)).fetchall()
    result=dict(zip(("id","title","priority","status","created_at","updated_at"),row))
    result["messages"]=[dict(zip(("id","sender","content","created_at"),m)) for m in messages]
    return result

def add_message(thread_id, sender, content):
    if sender not in ("luna","chatgpt","user"):
        raise ValueError("Unsupported sender")
    if not isinstance(content,str) or not 1<=len(content.strip())<=12000:
        raise ValueError("Invalid message")
    with core.connect() as db:
        _setup(db)
        state=db.execute("SELECT status FROM bridge_threads WHERE id=?",(thread_id,)).fetchone()
        if not state or state[0]=="closed":
            return False
        now=_now()
        db.execute("INSERT INTO bridge_messages(thread_id,sender,content,created_at) VALUES(?,?,?,?)",
                   (thread_id,sender,content.strip(),now))
        next_status="replied" if sender=="chatgpt" else "awaiting_relay" if sender=="luna" else state[0]
        db.execute("UPDATE bridge_threads SET status=?,updated_at=? WHERE id=?",
                   (next_status,now,thread_id))
        return True

def mark_relayed(thread_id):
    with core.connect() as db:
        _setup(db)
        cur=db.execute("""UPDATE bridge_threads SET status='awaiting_reply',updated_at=?
          WHERE id=? AND status='awaiting_relay'""",(_now(),thread_id))
        return cur.rowcount==1

def close_thread(thread_id):
    with core.connect() as db:
        _setup(db)
        cur=db.execute("UPDATE bridge_threads SET status='closed',updated_at=? WHERE id=? AND status!='closed'",
                       (_now(),thread_id))
        return cur.rowcount==1

def relay_message(thread):
    latest=next((m for m in reversed(thread["messages"]) if m["sender"]=="luna"),None)
    if latest is None:
        return ""
    return ("ORBIT / Luna bridge thread #"+str(thread["id"])+
            "\nPriority: "+thread["priority"]+
            "\nSubject: "+thread["title"]+
            "\nLuna's message:\n"+latest["content"]+
            "\n\nPlease respond with actionable technical guidance. You do not have direct access to this local ORBIT session.")
