"""Privacy-controlled conversation continuity for Luna.

Raw chat remains local. Cross-session model context comes only from summaries the
owner explicitly approves. Search is local/user-facing and skips messages that the
sensitivity classifier flags.
"""
import json
import re
from datetime import datetime, timezone

from luna import core
from luna.sensitivity_policy import classify

TAG=re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
WORD=re.compile(r"[A-Za-z0-9_'-]{3,}")

def _now():
    return datetime.now(timezone.utc).isoformat()

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS conversation_summaries (
      id INTEGER PRIMARY KEY,
      session TEXT NOT NULL,
      summary TEXT NOT NULL,
      tags TEXT NOT NULL DEFAULT '[]',
      status TEXT NOT NULL DEFAULT 'pending',
      source_message_count INTEGER NOT NULL,
      source_max_message_id INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      reviewed_at TEXT NOT NULL DEFAULT '')""")
    db.execute("""CREATE INDEX IF NOT EXISTS conversation_summary_session
                  ON conversation_summaries(session,status,id)""")

def _clean_tags(tags):
    if tags is None:
        return []
    if not isinstance(tags,(list,tuple)) or len(tags)>8:
        raise ValueError("Tags must be a short list")
    clean=[]
    for tag in tags:
        if not isinstance(tag,str):
            raise ValueError("Invalid tag")
        value=tag.strip().lower()
        if not TAG.fullmatch(value):
            raise ValueError("Invalid tag")
        if value not in clean:
            clean.append(value)
    return clean

def propose(session,summary,tags=None):
    if not isinstance(session,str) or not 1<=len(session)<=100:
        raise ValueError("Invalid session")
    if not isinstance(summary,str):
        raise ValueError("Summary must be text")
    summary=summary.strip()
    if not 30<=len(summary)<=2500:
        raise ValueError("Summary must be between 30 and 2500 characters")
    screening=classify(summary)
    if screening["sensitive"]:
        raise ValueError("Sensitive summaries must not enter Luna continuity memory")
    clean_tags=_clean_tags(tags)
    with core.connect() as db:
        _setup(db)
        stats=db.execute(
            "SELECT COUNT(*),COALESCE(MAX(id),0) FROM messages WHERE session=?",
            (session,)).fetchone()
        if not stats or stats[0]==0:
            raise ValueError("Session has no messages")
        existing=db.execute(
            """SELECT id FROM conversation_summaries
               WHERE session=? AND lower(summary)=lower(?)
               AND status IN ('pending','approved') LIMIT 1""",
            (session,summary)).fetchone()
        if existing:
            return {"id":existing[0],"created":False}
        cur=db.execute(
            """INSERT INTO conversation_summaries(
               session,summary,tags,status,source_message_count,source_max_message_id,created_at)
               VALUES(?,?,?,'pending',?,?,?)""",
            (session,summary,json.dumps(clean_tags,separators=(",",":")),stats[0],stats[1],_now()))
        return {"id":cur.lastrowid,"created":True}

def list_summaries(status=None,limit=60):
    if status not in (None,"pending","approved","rejected","revoked"):
        raise ValueError("Invalid summary status")
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("Invalid limit")
    with core.connect() as db:
        _setup(db)
        if status:
            rows=db.execute(
                """SELECT id,session,summary,tags,status,source_message_count,
                          source_max_message_id,created_at,reviewed_at
                   FROM conversation_summaries WHERE status=?
                   ORDER BY id DESC LIMIT ?""",(status,limit)).fetchall()
        else:
            rows=db.execute(
                """SELECT id,session,summary,tags,status,source_message_count,
                          source_max_message_id,created_at,reviewed_at
                   FROM conversation_summaries ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
    keys=("id","session","summary","tags","status","source_message_count",
          "source_max_message_id","created_at","reviewed_at")
    result=[]
    for row in rows:
        item=dict(zip(keys,row))
        item["tags"]=json.loads(item["tags"])
        result.append(item)
    return result

def decide(summary_id,approve):
    if type(approve) is not bool:
        raise ValueError("Approval must be boolean")
    state="approved" if approve else "rejected"
    with core.connect() as db:
        _setup(db)
        cur=db.execute(
            """UPDATE conversation_summaries SET status=?,reviewed_at=?
               WHERE id=? AND status='pending'""",
            (state,_now(),summary_id))
        return cur.rowcount==1

def approved_context(query="",limit=5):
    if not isinstance(query,str) or len(query)>2000:
        raise ValueError("Invalid continuity query")
    if type(limit) is not int or not 1<=limit<=10:
        raise ValueError("Invalid limit")
    terms={m.group(0).lower() for m in WORD.finditer(query)}
    with core.connect() as db:
        _setup(db)
        rows=db.execute(
            """SELECT id,session,summary,tags,created_at
               FROM conversation_summaries
               WHERE status='approved' ORDER BY id DESC LIMIT 100""").fetchall()
    scored=[]
    for row in rows:
        tags=json.loads(row[3])
        haystack=(row[2]+" "+" ".join(tags)).lower()
        score=sum(1 for term in terms if term in haystack)
        if terms and score==0:
            continue
        scored.append((score,row))
    scored.sort(key=lambda item:(item[0],item[1][0]),reverse=True)
    return [{"id":row[0],"session":row[1],"summary":row[2],
             "tags":json.loads(row[3]),"created_at":row[4]}
            for _score,row in scored[:limit]]

def session_cards(limit=30):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("Invalid limit")
    with core.connect() as db:
        rows=db.execute(
            """SELECT session,COUNT(*),MAX(created_at),MAX(id)
               FROM messages GROUP BY session ORDER BY MAX(id) DESC LIMIT ?""",
            (limit,)).fetchall()
        cards=[]
        for session,count,updated,max_id in rows:
            first=db.execute(
                """SELECT content FROM messages
                   WHERE session=? AND role='user' ORDER BY id LIMIT 1""",
                (session,)).fetchone()
            title="Conversation"
            if first:
                text=first[0].strip().replace("\n"," ")
                if classify(text)["sensitive"]:
                    title="Private conversation"
                elif text:
                    title=text[:70]+("…" if len(text)>70 else "")
            cards.append({"session":session,"title":title,"message_count":count,
                          "updated_at":updated,"last_message_id":max_id})
    return cards

def search_history(query,limit=20):
    if not isinstance(query,str):
        raise ValueError("Query must be text")
    query=query.strip()
    if not 2<=len(query)<=120:
        raise ValueError("Query must be between 2 and 120 characters")
    if type(limit) is not int or not 1<=limit<=50:
        raise ValueError("Invalid limit")
    terms={m.group(0).lower() for m in WORD.finditer(query)}
    if not terms:
        terms={query.lower()}
    with core.connect() as db:
        rows=db.execute(
            """SELECT id,session,role,content,created_at
               FROM messages ORDER BY id DESC LIMIT 1000""").fetchall()
    matches=[]
    for message_id,session,role,content,created_at in rows:
        if classify(content)["sensitive"]:
            continue
        lower=content.lower()
        score=sum(1 for term in terms if term in lower)
        if score==0:
            continue
        compact=" ".join(content.split())
        snippet=compact[:240]+("…" if len(compact)>240 else "")
        matches.append({"message_id":message_id,"session":session,"role":role,
                        "snippet":snippet,"created_at":created_at,"score":score})
    matches.sort(key=lambda item:(item["score"],item["message_id"]),reverse=True)
    return matches[:limit]

def status():
    with core.connect() as db:
        _setup(db)
        counts=dict(db.execute(
            "SELECT status,COUNT(*) FROM conversation_summaries GROUP BY status").fetchall())
    return {
        "pending":counts.get("pending",0),
        "approved":counts.get("approved",0),
        "rejected":counts.get("rejected",0),
        "revoked":counts.get("revoked",0),
        "raw_history_searchable_locally":True,
        "sensitive_search_results_hidden":True,
        "cross_session_model_context":"approved_summaries_only",
    }


_STOPWORDS=frozenset({
    "the","and","that","this","with","from","have","want","your","about","into","just",
    "like","what","when","where","which","would","could","should","there","their","they",
    "them","then","than","been","were","will","make","need","does","doing","some","more",
    "very","much","only","also","because","while","after","before","over","under","user",
    "luna","chat","conversation","please","help"
})

def _checkpoint_tags(messages):
    counts={}
    for message in messages:
        for match in WORD.finditer(message.lower()):
            word=match.group(0)
            if word in _STOPWORDS or len(word)>28:
                continue
            counts[word]=counts.get(word,0)+1
    ranked=sorted(counts,key=lambda word:(counts[word],len(word),word),reverse=True)
    return [word for word in ranked[:6] if TAG.fullmatch(word)]

def maybe_checkpoint(session,min_new_user_messages=8):
    """Create one pending local checkpoint when enough new safe user messages exist.

    No model call occurs. The checkpoint is not eligible for Luna context until the
    owner explicitly approves it.
    """
    if not isinstance(session,str) or not 1<=len(session)<=100:
        raise ValueError("Invalid session")
    if type(min_new_user_messages) is not int or not 4<=min_new_user_messages<=30:
        raise ValueError("Invalid checkpoint threshold")
    with core.connect() as db:
        _setup(db)
        open_candidate=db.execute(
            """SELECT id FROM conversation_summaries
               WHERE session=? AND status='pending' ORDER BY id DESC LIMIT 1""",
            (session,)).fetchone()
        if open_candidate:
            return {"created":False,"reason":"pending_review","id":open_candidate[0]}
        prior=db.execute(
            """SELECT COALESCE(MAX(source_max_message_id),0)
               FROM conversation_summaries
               WHERE session=? AND status IN ('approved','rejected')""",
            (session,)).fetchone()
        after_id=prior[0] if prior else 0
        rows=db.execute(
            """SELECT id,content FROM messages
               WHERE session=? AND role='user' AND id>?
               ORDER BY id ASC""",(session,after_id)).fetchall()
    if len(rows)<min_new_user_messages:
        return {"created":False,"reason":"threshold"}
    safe=[]
    for _message_id,message in rows[-12:]:
        compact=" ".join(message.split()).strip()
        if not compact or classify(compact)["sensitive"]:
            continue
        safe.append(compact[:260])
    if len(safe)<3:
        return {"created":False,"reason":"insufficient_safe_content"}
    selected=safe[-6:]
    summary=("Conversation checkpoint pending owner review. The user recently discussed: " +
             " | ".join(selected))
    summary=summary[:2450]
    tags=_checkpoint_tags(selected)
    created=propose(session,summary,tags)
    return {"created":created["created"],"id":created["id"],
            "reason":"created" if created["created"] else "duplicate",
            "model_called":False,"approved":False}


def context_for_session(session,query="",limit=5):
    """Return the latest approved current-session checkpoint plus relevant older context."""
    if not isinstance(session,str) or not 1<=len(session)<=100:
        raise ValueError("Invalid session")
    if type(limit) is not int or not 1<=limit<=10:
        raise ValueError("Invalid limit")
    with core.connect() as db:
        _setup(db)
        current=db.execute(
            """SELECT id,session,summary,tags,created_at
               FROM conversation_summaries
               WHERE session=? AND status='approved'
               ORDER BY id DESC LIMIT 1""",(session,)).fetchone()
    selected=[]
    seen=set()
    if current:
        item={"id":current[0],"session":current[1],"summary":current[2],
              "tags":json.loads(current[3]),"created_at":current[4]}
        selected.append(item);seen.add(item["id"])
    for item in approved_context(query,limit=limit):
        if item["id"] in seen:
            continue
        selected.append(item);seen.add(item["id"])
        if len(selected)>=limit:
            break
    return selected[:limit]


def revoke(summary_id):
    """Remove an approved summary from future Luna context without deleting history."""
    with core.connect() as db:
        _setup(db)
        cur=db.execute(
            """UPDATE conversation_summaries
               SET status='revoked',reviewed_at=?
               WHERE id=? AND status='approved'""",
            (_now(),summary_id))
        return cur.rowcount==1
