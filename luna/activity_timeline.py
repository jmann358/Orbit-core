"""Privacy-aware unified activity timeline for ORBIT.

This module reads durable metadata only. It never returns code candidate source,
conversation summary text, credentials, job detail payloads, or private watchdog data.
"""
import json
from datetime import datetime, timezone

from luna import core
from luna.sensitivity_policy import classify

def _table_exists(db,name):
    row=db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,)).fetchone()
    return bool(row)

def _safe_label(text,fallback,max_length=120):
    if not isinstance(text,str):
        return fallback
    compact=" ".join(text.split()).strip()
    if not compact or classify(compact)["sensitive"]:
        return fallback
    return compact[:max_length]

def snapshot(limit=100):
    if type(limit) is not int or not 1<=limit<=200:
        raise ValueError("Invalid activity limit")
    events=[]
    with core.connect() as db:
        if _table_exists(db,"work_items"):
            rows=db.execute("""SELECT id,title,state,created_at,updated_at
                               FROM work_items ORDER BY id DESC LIMIT 200""").fetchall()
            for row in rows:
                events.append({
                    "event_id":"job:"+str(row[0]),
                    "kind":"job",
                    "label":_safe_label(row[1],"Private task"),
                    "state":row[2],
                    "timestamp":row[4] or row[3],
                    "detail":None,
                })
        if _table_exists(db,"agent_runs"):
            rows=db.execute("""SELECT id,task,status,summary,created_at
                               FROM agent_runs ORDER BY id DESC LIMIT 200""").fetchall()
            for row in rows:
                events.append({
                    "event_id":"run:"+str(row[0]),
                    "kind":"agent_run",
                    "label":_safe_label(row[1],"Luna activity"),
                    "state":row[2],
                    "timestamp":row[4],
                    "detail":_safe_label(row[3],"Sensitive detail hidden",240),
                })
        if _table_exists(db,"development_candidates"):
            rows=db.execute("""SELECT id,path,attempt_number,state,updated_at
                               FROM development_candidates ORDER BY id DESC LIMIT 100""").fetchall()
            for row in rows:
                events.append({
                    "event_id":"candidate:"+str(row[0]),
                    "kind":"sandbox_validation",
                    "label":"Validate "+row[1]+" · attempt "+str(row[2]),
                    "state":row[3],
                    "timestamp":row[4],
                    "detail":"Isolated validation only · live source unchanged",
                })
        if _table_exists(db,"conversation_summaries"):
            rows=db.execute("""SELECT id,status,created_at,reviewed_at
                               FROM conversation_summaries ORDER BY id DESC LIMIT 100""").fetchall()
            for row in rows:
                events.append({
                    "event_id":"continuity:"+str(row[0]),
                    "kind":"continuity",
                    "label":"Conversation checkpoint",
                    "state":row[1],
                    "timestamp":row[3] or row[2],
                    "detail":"Summary text hidden from activity feed",
                })

    events.sort(key=lambda item:item["timestamp"] or "",reverse=True)
    events=events[:limit]
    active_states={"queued","running","retry_allowed"}
    attention_states={"attention","blocked","failed","needs_attention"}
    counts={
        "active":sum(item["state"] in active_states for item in events),
        "attention":sum(item["state"] in attention_states for item in events),
        "completed":sum(item["state"] in {"completed","passed","approved"} for item in events),
    }
    status=("Needs Attention" if counts["attention"] else
            "Working" if counts["active"] else "Idle")
    return {
        "status":status,
        "counts":counts,
        "events":events,
        "limited_to_recent":limit,
        "payloads_excluded":True,
        "watchdog_included":False,
        "generated_at":datetime.now(timezone.utc).isoformat(),
    }
