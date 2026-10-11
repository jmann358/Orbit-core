"""Privacy-aware unified activity timeline for ORBIT.

Reads durable metadata only. Never returns code candidate source, conversation text,
credentials, private watchdog data, bridge message bodies, or request payloads.
"""
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

def _event(event_id,kind,label,state,timestamp,detail=None,priority="normal"):
    return {
        "event_id":event_id,
        "kind":kind,
        "label":label,
        "state":state,
        "timestamp":timestamp,
        "detail":detail,
        "priority":priority,
    }

def snapshot(limit=100):
    if type(limit) is not int or not 1<=limit<=200:
        raise ValueError("Invalid activity limit")
    events=[]
    with core.connect() as db:
        if _table_exists(db,"work_items"):
            rows=db.execute("""SELECT id,title,state,created_at,updated_at
                               FROM work_items ORDER BY id DESC LIMIT 200""").fetchall()
            for row in rows:
                events.append(_event(
                    "job:"+str(row[0]),"job",
                    _safe_label(row[1],"Private task"),row[2],row[4] or row[3]))

        if _table_exists(db,"agent_runs"):
            rows=db.execute("""SELECT id,task,status,summary,created_at
                               FROM agent_runs ORDER BY id DESC LIMIT 200""").fetchall()
            for row in rows:
                events.append(_event(
                    "run:"+str(row[0]),"agent_run",
                    _safe_label(row[1],"Luna activity"),row[2],row[4],
                    _safe_label(row[3],"Sensitive detail hidden",240)))

        if _table_exists(db,"development_candidates"):
            rows=db.execute("""SELECT id,path,attempt_number,state,updated_at
                               FROM development_candidates ORDER BY id DESC LIMIT 100""").fetchall()
            for row in rows:
                events.append(_event(
                    "candidate:"+str(row[0]),"sandbox_validation",
                    "Validate "+row[1]+" · attempt "+str(row[2]),row[3],row[4],
                    "Isolated validation only · live source unchanged"))

        if _table_exists(db,"conversation_summaries"):
            rows=db.execute("""SELECT id,status,created_at,reviewed_at
                               FROM conversation_summaries ORDER BY id DESC LIMIT 100""").fetchall()
            for row in rows:
                events.append(_event(
                    "continuity:"+str(row[0]),"continuity",
                    "Conversation checkpoint",row[1],row[3] or row[2],
                    "Summary text hidden from activity feed"))

        if _table_exists(db,"agent_goals"):
            rows=db.execute("""SELECT id,objective,state,created_at,updated_at
                               FROM agent_goals ORDER BY id DESC LIMIT 100""").fetchall()
            for row in rows:
                events.append(_event(
                    "goal:"+str(row[0]),"goal",
                    _safe_label(row[1],"Private goal"),row[2],row[4] or row[3],
                    "Goal details are not expanded in the activity feed"))

        if _table_exists(db,"bridge_threads"):
            rows=db.execute("""SELECT id,title,priority,status,created_at,updated_at
                               FROM bridge_threads ORDER BY id DESC LIMIT 100""").fetchall()
            for row in rows:
                events.append(_event(
                    "bridge:"+str(row[0]),"bridge",
                    _safe_label(row[1],"Private bridge thread"),row[3],row[5] or row[4],
                    "User-mediated bridge · message bodies hidden",row[2]))

        if _table_exists(db,"luna_requests"):
            rows=db.execute("""SELECT id,kind,priority,title,status,created_at,resolved_at
                               FROM luna_requests ORDER BY id DESC LIMIT 100""").fetchall()
            for row in rows:
                events.append(_event(
                    "request:"+str(row[0]),"owner_request",
                    _safe_label(row[3],"Private owner request"),row[4],row[6] or row[5],
                    row[1].replace("_"," ")+" · request payload hidden",row[2]))

    events.sort(key=lambda item:item["timestamp"] or "",reverse=True)
    events=events[:limit]

    active_states={
        "queued","running","retry_allowed","proposed","approved",
        "awaiting_relay","awaiting_reply","open","draft"
    }
    attention_states={"attention","blocked","failed","needs_attention"}
    for item in events:
        item["needs_attention"]=(
            item["state"] in attention_states or
            (item["kind"]=="owner_request" and item["state"]=="open" and item["priority"]=="high") or
            (item["kind"]=="bridge" and item["state"]=="awaiting_relay" and item["priority"]=="high")
        )
    counts={
        "active":sum(item["state"] in active_states for item in events),
        "attention":sum(item["needs_attention"] for item in events),
        "completed":sum(item["state"] in {
            "completed","passed","approved","replied","closed","acknowledged","rejected","revoked"
        } for item in events),
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

def current(limit=100):
    """Return one concise current-status card from the safe timeline."""
    data=snapshot(limit)
    events=data["events"]
    attention=next((item for item in events if item["needs_attention"]),None)
    active=next((item for item in events if item["state"] in {
        "queued","running","retry_allowed","proposed","approved",
        "awaiting_relay","awaiting_reply","open","draft"
    }),None)
    recent=events[0] if events else None
    focus=attention or active or recent
    if focus is None:
        headline="Luna is idle. No recorded work is waiting."
    elif attention:
        headline="Needs attention: "+focus["label"]
    elif active:
        headline="Working on: "+focus["label"]
    else:
        headline="Latest activity: "+focus["label"]
    return {
        "status":data["status"],
        "headline":headline,
        "focus":focus,
        "counts":data["counts"],
        "generated_at":data["generated_at"],
        "payloads_excluded":True,
    }
