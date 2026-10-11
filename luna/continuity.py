"""Deterministic retrieval from Luna's persistent SQLite conversation archive.

This is read-only search, NOT approved memory or an instruction source.
No cloud calls, embeddings, summarization, or automatic approval.
"""
import re
import sqlite3
from pathlib import Path

STOP = frozenset(
    "the and for that this with from what when where have your you are was were "
    "how why can not but about into just then them they she him her his our its "
    "whatsoever there here also will would could should".split()
)
MAX_SCAN = 2000
MAX_EXCERPT = 700
MAX_CHARS = 3500


def _terms(text):
    return set(re.findall(r"[a-z0-9]{3,}", text.casefold())) - STOP


def recall(db_path, session, query, limit=5, *, exclude_ids=(), other_sessions=True):
    """Return ranked, source-attributed older conversation excerpts.

    The caller decides if and where to display these. Excerpts are never
    stored as approved memory or sent to a provider by this module.
    """
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 240:
        raise ValueError("Query must be 1-240 characters")
    if not isinstance(session, str) or not 1 <= len(session) <= 100:
        raise ValueError("Invalid session")
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("Limit must be 1-10")
    if not isinstance(other_sessions, bool):
        raise ValueError("Invalid scope")
    words = _terms(query)
    if not words:
        return []
    if not Path(db_path).is_file():
        return []
    skipped = set(exclude_ids)
    with sqlite3.connect(db_path) as db:
        if other_sessions:
            rows = db.execute(
                "SELECT id,session,role,content,created_at FROM messages "
                "WHERE role IN ('user','assistant') ORDER BY id DESC LIMIT ?",
                (MAX_SCAN,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id,session,role,content,created_at FROM messages "
                "WHERE session=? AND role IN ('user','assistant') "
                "ORDER BY id DESC LIMIT ?",
                (session, MAX_SCAN),
            ).fetchall()
    found = []
    for ident, origin, role, content, created in rows:
        if ident in skipped:
            continue
        fragment = content[:MAX_EXCERPT]
        score = len(words & _terms(fragment))
        if score:
            found.append((score, ident, {
                "id": ident, "session": origin, "role": role,
                "content": fragment, "created_at": created,
            }))
    found.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    result, remaining = [], MAX_CHARS
    for _, _, item in found:
        if remaining <= 0 or len(result) >= limit:
            break
        fragment = item["content"][:remaining]
        result.append({**item, "content": fragment})
        remaining -= len(fragment)
    return result


def render_context(excerpts):
    """Label history as untrusted source material, not instructions or facts."""
    chunks = []
    for item in excerpts[:5]:
        role = item["role"] if item["role"] in ("user", "assistant") else "unknown"
        chunks.append(
            "Historical message " + str(item["id"]) +
            " (session " + str(item["session"])[:100] + ", " + role + "):\n" +
            str(item["content"])[:MAX_EXCERPT]
        )
    return "\n\n".join(chunks)
