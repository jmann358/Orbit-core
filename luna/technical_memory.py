"""Project decision ledger separate from personal memories and model prompts."""
from datetime import datetime, timezone
from luna import core

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS technical_decisions (
      id INTEGER PRIMARY KEY, topic TEXT NOT NULL, decision TEXT NOT NULL,
      source TEXT NOT NULL, created_at TEXT NOT NULL)""")

def record(topic, decision, source="owner"):
    if source not in ("owner","approved_bridge","verified_repo"):
        raise ValueError("Untrusted technical memory source")
    if not isinstance(topic,str) or not 3<=len(topic.strip())<=120:
        raise ValueError("Invalid topic")
    if not isinstance(decision,str) or not 5<=len(decision.strip())<=3000:
        raise ValueError("Invalid decision")
    with core.connect() as db:
        _setup(db)
        existing=db.execute("""SELECT id FROM technical_decisions
          WHERE topic=? AND decision=? LIMIT 1""",(topic.strip(),decision.strip())).fetchone()
        if existing:
            return {"id":existing[0],"created":False}
        cur=db.execute("""INSERT INTO technical_decisions
          (topic,decision,source,created_at) VALUES(?,?,?,?)""",
          (topic.strip(),decision.strip(),source,datetime.now(timezone.utc).isoformat()))
        return {"id":cur.lastrowid,"created":True}

def list_decisions(limit=50):
    with core.connect() as db:
        _setup(db)
        rows=db.execute("""SELECT id,topic,decision,source,created_at FROM technical_decisions
          ORDER BY id DESC LIMIT ?""",(min(max(int(limit),1),100),)).fetchall()
    return [dict(zip(("id","topic","decision","source","created_at"),r)) for r in rows]
