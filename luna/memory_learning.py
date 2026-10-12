"""Review-only structured learning from already saved user chat turns.

No model calls, no automated personal memory approval, no outbound transfers.
Only explicitly patterned user statements may be queued for user review.
"""
import re
from luna import core
from luna.continuity import INTERNAL_SESSION_PREFIXES
from luna.memory_suggestions import BLOCKED

MAX_SCAN = 200
MAX_PREVIEW = 12
MAX_CANDIDATE = 300

PATTERNS = (
    re.compile(r"^\s*(?:for\s+(?:orbit|luna)[,:]?\s+)(.{12,300})$", re.I | re.S),
    re.compile(r"^\s*(?:i\s+prefer\s+)(.{12,300})$", re.I | re.S),
    re.compile(r"^\s*(?:luna\s+should\s+)(.{12,300})$", re.I | re.S),
    re.compile(r"^\s*(?:i\s+want\s+luna\s+to\s+)(.{12,300})$", re.I | re.S),
)

def _candidate(text):
    if not isinstance(text, str) or len(text) > 500:
        return None
    # Keep original user wording; never infer hidden facts.
    for pattern in PATTERNS:
        match = pattern.fullmatch(text.strip())
        if match:
            normalized = " ".join(text.strip().split()).rstrip(".")
            if 12 <= len(normalized) <= MAX_CANDIDATE and not BLOCKED.search(normalized):
                return normalized
    return None


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS memory_learning_sources (
        id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL UNIQUE,
        message_id INTEGER NOT NULL UNIQUE, session TEXT NOT NULL,
        created_at TEXT NOT NULL)""")


def preview(session, limit=8):
    if not isinstance(session, str) or not 1 <= len(session) <= 100:
        raise ValueError("Invalid session")
    if session.startswith(INTERNAL_SESSION_PREFIXES):
        return []
    if type(limit) is not int or not 1 <= limit <= MAX_PREVIEW:
        raise ValueError("Invalid limit")
    with core.connect() as db:
        rows = db.execute(
            "SELECT id,content,created_at FROM messages WHERE session=? "
            "AND role='user' ORDER BY id DESC LIMIT ?", (session, MAX_SCAN),
        ).fetchall()
        previous = {text.casefold() for (text,) in db.execute(
            "SELECT content FROM memory_candidates"
        )}
    results = []
    seen = set()
    for ident, text, at in rows:
        content = _candidate(text)
        if not content:
            continue
        folded = content.casefold()
        if folded in previous or folded in seen:
            continue
        seen.add(folded)
        results.append({
            "message_id": ident, "session": session,
            "content": content, "source_created_at": at,
            "state": "preview_only", "requires_approval": True,
            "source_role": "user",
        })
        if len(results) >= limit:
            break
    return results


def suggest(message_id):
    """Explicitly queue exactly one source-backed candidate; never approve it."""
    if type(message_id) is not int or message_id < 1:
        raise ValueError("Invalid message id")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        row = db.execute(
            "SELECT session,role,content FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
        if not row or row[1] != "user" or row[0].startswith(INTERNAL_SESSION_PREFIXES):
            raise ValueError("Only original user messages qualify")
        content = _candidate(row[2])
        if not content:
            raise ValueError("Message is not eligible for memory review")
        if db.execute(
            "SELECT 1 FROM memory_candidates WHERE lower(content)=lower(?)",
            (content,),
        ).fetchone():
            raise ValueError("Already considered this candidate")
        cur = db.execute(
            "INSERT INTO memory_candidates(content,created_at) VALUES(?,?)",
            (content, core.timestamp()),
        )
        _setup(db)
        db.execute(
            "INSERT INTO memory_learning_sources(candidate_id,message_id,session,"
            "created_at) VALUES(?,?,?,?)",
            (cur.lastrowid, message_id, row[0], core.timestamp()),
        )
        return {
            "candidate_id": cur.lastrowid, "source_message_id": message_id,
            "session": row[0], "status": "pending", "approved": False,
        }


def sources(limit=30):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid limit")
    with core.connect() as db:
        _setup(db)
        rows = db.execute(
            "SELECT s.candidate_id,s.message_id,s.session,"
            "c.content,c.status,s.created_at "
            "FROM memory_learning_sources s JOIN memory_candidates c "
            "ON c.id=s.candidate_id ORDER BY s.id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [
        dict(zip(("candidate_id","message_id","session","content",
                  "status","created_at"), row)) for row in rows
    ]
