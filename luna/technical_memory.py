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

def search_decisions(query, limit=20):
    """Case-insensitive, parameterized search over approved technical decisions."""
    if not isinstance(query,str) or not 2<=len(query.strip())<=120:
        raise ValueError("Search query must contain 2-120 characters")
    if type(limit) is not int or not 1<=limit<=50:
        raise ValueError("Search limit must be 1-50")
    needle=query.strip().casefold()
    # Fetch bounded rows and filter in Python so wildcard characters stay literal.
    with core.connect() as db:
        _setup(db)
        rows=db.execute("""SELECT id,topic,decision,source,created_at
            FROM technical_decisions ORDER BY id DESC LIMIT 1000""").fetchall()
    fields=("id","topic","decision","source","created_at")
    return [dict(zip(fields,row)) for row in rows
            if needle in row[1].casefold() or needle in row[2].casefold()][:limit]
