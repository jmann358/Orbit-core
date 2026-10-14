"""Weaver — the memory miner.

Lineage (Headhunter dossier #3): Ruflo's memory-specialist and typed
memory — the insight that memory is typed by lifespan, not just
stored. Rebuilt as a design, not adopted code.

Archivist FILES memories; Weaver READS them back and mines them for
patterns, turning dead knowledge into proposals. Jason's rule ("Luna
remembers only approved context") is honored, not worked around:

- Weaver is read-only over memory_entries and the mission table.
- Weaver PROPOSES patterns only. A proposal is filed as memory ONLY
  through Archivist's file_memory with a NAMED approver — the call
  goes through the Archivist's own guard, never a direct INSERT.
  A blank approver is refused before anything is written.
- Weaver never edits, never retires, never re-scores a memory.
  Editing and retiring belong to Archivist and Jason.
- Every proposal cites the exact records it drew from (counts +
  memory ids), owner-scoped; guest namespaces would get their own
  mines, never cross-owner reads.

Mining is deliberately simple and deterministic: recurring
significant tokens (>= 5 chars) across memory texts and mission
titles. A token becomes a theme when it appears at least twice in at
least two distinct records. This is pattern SUGGESTION, not machine
learning — Jason approves or dismisses each one, and the hit rate is
the honest measure.

Probation: started 2026-10-14, review due 2026-11-13. Mentor grades:
mine the existing records and file 3 cited proposals; the
approve/reject hit rate; one full weekly run folded into Herald's
briefing; after 30 days, whether approved weavings reduced repeat
work.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import archivist as AR
from luna_v2 import missions as M
from luna_v2.store import Store


class WeaverError(M.LunaError):
    """Base error for the memory miner's guard rails."""


class ProposalNotFound(WeaverError):
    """No pattern proposal with that id exists for the owner."""


class ProposalRefused(WeaverError):
    """A proposal action was refused — blank approver, wrong state."""


PROPOSAL_STATUSES = ("proposed", "filed", "dismissed")

# A theme: a significant token (>= 5 chars) in at least this many
# records. Below it, the thread is noise.
_TOKEN_MIN_LEN = 5
_THEME_MIN_RECORDS = 2
_THEME_MIN_COUNT = 2
_MAX_NEW_PER_MINE = 5

# Words that recur everywhere in Luna's records and would fake themes.
_STOPWORDS = frozenset({
    "about", "after", "again", "before", "could", "every", "first",
    "from", "have", "luna", "orbit", "jason", "mission", "missions",
    "other", "should", "their", "there", "these", "those", "through",
    "under", "which", "with", "would", "your",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS pattern_proposals (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               pattern TEXT NOT NULL,
               evidence TEXT NOT NULL DEFAULT '{}',
               status TEXT NOT NULL DEFAULT 'proposed'
                   CHECK (status IN ('proposed', 'filed', 'dismissed')),
               filed_memory_id INTEGER,
               created_at TEXT NOT NULL)"""
    )
    store._db.commit()


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]{5,}", (text or "").lower())
            if t not in _STOPWORDS]


def _mineable_records(store: Store, owner: str) -> list[dict]:
    """Read-only sweep of what Weaver may read: active memory entries
    and mission titles. Never retired entries, never other owners."""
    records = []
    for mem in AR.list_memories(store, owner):
        records.append({"kind": "memory", "id": mem["id"],
                        "text": mem["text"]})
    rows = store._db.execute(
        "SELECT id, title FROM missions WHERE owner = ?",
        (owner,)).fetchall()
    for r in rows:
        records.append({"kind": "mission", "id": r["id"],
                        "text": r["title"]})
    return records


def mine(store: Store, owner: str) -> list:
    """Mine the owner's records for recurring themes. Deterministic:
    significant tokens (>= 5 chars) appearing >= 2 times across >= 2
    distinct records become pattern proposals, newest mines deduped
    against already proposed/filed patterns. At most
    _MAX_NEW_PER_MINE new proposals per run. Returns the new rows;
    an empty list is an honest 'no pattern yet', not a failure."""
    _ensure_schema(store)
    records = _mineable_records(store, owner)
    seen = {r["pattern"] for r in store._db.execute(
        "SELECT pattern FROM pattern_proposals WHERE owner = ? AND "
        "status IN ('proposed', 'filed')", (owner,)).fetchall()}
    # token -> [count, {record keys}]
    tally: dict[str, list] = {}
    for rec in records:
        key = (rec["kind"], rec["id"])
        for tok in _tokens(rec["text"]):
            slot = tally.setdefault(tok, [0, set()])
            slot[0] += 1
            slot[1].add(key)
    new = []
    for tok in sorted(tally):
        count, keys = tally[tok]
        if count < _THEME_MIN_COUNT or len(keys) < _THEME_MIN_RECORDS:
            continue
        pattern = (f"theme '{tok}' recurs {count} time(s) across "
                   f"{len(keys)} record(s)")
        if pattern in seen:
            continue
        evidence = {"token": tok, "count": count,
                    "records": [{"kind": k, "id": i}
                                for k, i in sorted(keys)]}
        store._db.execute(
            "INSERT INTO pattern_proposals (owner, pattern, evidence, "
            "status, created_at) VALUES (?, ?, ?, 'proposed', ?)",
            (owner, pattern, json.dumps(evidence), _now()))
        store._db.commit()
        seen.add(pattern)
        new.append(store._db.execute(
            "SELECT * FROM pattern_proposals WHERE id = "
            "last_insert_rowid()").fetchone())
        if len(new) >= _MAX_NEW_PER_MINE:
            break
    return new


def list_proposals(store: Store, owner: str,
                   status: str | None = None) -> list:
    _ensure_schema(store)
    if status is not None:
        if status not in PROPOSAL_STATUSES:
            raise WeaverError(
                f"status must be one of {PROPOSAL_STATUSES}, "
                f"got {status!r}")
        where = "owner = ? AND status = ?"
        args: tuple = (owner, status)
    else:
        where = "owner = ?"
        args = (owner,)
    return store._db.execute(
        f"SELECT * FROM pattern_proposals WHERE {where} "
        "ORDER BY id DESC", args).fetchall()


def _proposal_or_raise(store: Store, owner: str, proposal_id: int) -> Row:
    row = store._db.execute(
        "SELECT * FROM pattern_proposals WHERE id = ? AND owner = ?",
        (proposal_id, owner)).fetchone()
    if row is None:
        raise ProposalNotFound(
            f"no pattern proposal {proposal_id} for owner {owner!r}")
    return row


def file_pattern(store: Store, owner: str, proposal_id: int,
                 approved_by: str) -> Row:
    """File a proposed pattern as memory — ONLY through Archivist's
    file_memory, with a NAMED approver. Weaver never writes
    memory_entries directly (pinned by test). Refusals (nothing
    written, proposal untouched): blank approver; proposal not
    'proposed'. Archivist's own guard still bites underneath."""
    _ensure_schema(store)
    by = (approved_by or "").strip()
    if not by:
        raise ProposalRefused(
            "a pattern needs a named approver before it becomes "
            "memory — Luna remembers only approved context")
    row = _proposal_or_raise(store, owner, proposal_id)
    if row["status"] != "proposed":
        raise ProposalRefused(
            f"proposal {proposal_id} is {row['status']} — only proposed "
            "patterns can be filed")
    evidence = json.loads(row["evidence"] or "{}")
    text = (f"Weaver pattern: {row['pattern']}. Evidence: "
            f"{json.dumps(evidence)}.")
    memory_id = AR.file_memory(
        store, owner, text, approved_by=by,
        source="weaver pattern proposal",
        approval_note=f"pattern proposal {proposal_id} approved by {by}")
    store._db.execute(
        "UPDATE pattern_proposals SET status = 'filed', "
        "filed_memory_id = ? WHERE id = ? AND owner = ?",
        (memory_id, proposal_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM pattern_proposals WHERE id = ?",
        (proposal_id,)).fetchone()


def dismiss(store: Store, owner: str, proposal_id: int) -> Row:
    """Dismiss a proposal — Jason's 'not a pattern' verdict. The row
    stays (history is never rewritten), status moves to 'dismissed'."""
    _ensure_schema(store)
    row = _proposal_or_raise(store, owner, proposal_id)
    store._db.execute(
        "UPDATE pattern_proposals SET status = 'dismissed' "
        "WHERE id = ? AND owner = ?", (proposal_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM pattern_proposals WHERE id = ?",
        (proposal_id,)).fetchone()
