"""Archivist — Luna's memory archivist.

Jason's core rule for Luna is "remembers only approved context." The
Archivist is the gate that makes that rule structural instead of
aspirational: a memory excerpt CANNOT be filed without a named approver,
and every entry permanently records who approved it and why, so any
entry can always answer "who approved this, and why."

Design, deliberate:
- One table, owned by this module (`CREATE TABLE IF NOT EXISTS`;
  store.py is never touched).
- Filing is a hard gate, not a warning: empty or blank `approved_by`
  (or empty text) raises and stores NOTHING. No silent entries.
- Memories are owner-namespaced. Search and list never cross owners.
- Retirement is a soft delete: the row persists with a reason, so the
  audit trail survives. Retiring a missing id, another owner's entry,
  or an already-retired entry is a clear error — silence would hide
  mistakes.
- Zero provider calls, zero network. Archivist stores and retrieves;
  it never summarizes, ranks, or invents.

Stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from luna_v2 import missions as M
from luna_v2.store import Store


class ArchivistError(M.LunaError):
    """Base error for the Archivist."""


class MemoryNotFound(ArchivistError):
    """No memory entry with that id."""


class MemoryAccessDenied(ArchivistError):
    """That entry belongs to another owner."""


class MemoryRetired(ArchivistError):
    """That entry is already retired."""


# ---------------------------------------------------------------------------
# Schema (owned by this module; store.py untouched)
# ---------------------------------------------------------------------------
MEMORY_ENTRIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    text          TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT '',
    approved_by   TEXT NOT NULL,
    approval_note TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    retired_at    TEXT,
    retire_reason TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(MEMORY_ENTRIES_SCHEMA)
    store._db.commit()


def _entry_or_raise(store: Store, entry_id: int):
    row = store._db.execute(
        "SELECT * FROM memory_entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise MemoryNotFound(f"memory entry {entry_id} not found")
    return row


# ---------------------------------------------------------------------------
# Filing (the hard gate)
# ---------------------------------------------------------------------------
def file_memory(store: Store, owner: str, text: str, *,
                approved_by: str, source: str = "",
                approval_note: str = "") -> int:
    """File an approved memory excerpt into the owner's namespace.

    Returns the new entry id. Filing WITHOUT a named approver — or
    with empty text — is impossible: it raises ArchivistError and
    stores nothing. The approver and note ride on the entry forever.
    """
    _ensure_schema(store)
    approved_by = (approved_by or "").strip()
    if not approved_by:
        raise ArchivistError(
            "cannot file a memory without a named approver: "
            "Luna remembers only approved context")
    text = (text or "").strip()
    if not text:
        raise ArchivistError("cannot file an empty memory excerpt")
    cur = store._db.execute(
        "INSERT INTO memory_entries "
        "(owner, text, source, approved_by, approval_note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (owner, text, (source or "").strip(),
         approved_by, (approval_note or "").strip(), _now()))
    store._db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Retrieval (owner-scoped, retired excluded by default)
# ---------------------------------------------------------------------------
def _like_escape(text: str) -> str:
    # Escape LIKE wildcards so a search for "100%" means 100%, literally.
    return (text.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_"))


def search_memory(store: Store, owner: str, query: str) -> list:
    """Newest-first live entries whose text contains `query`
    (case-insensitive substring). No match is an empty list, not an
    error. Another owner's entries are never returned."""
    _ensure_schema(store)
    query = (query or "").strip()
    if not query:
        return []
    rows = store._db.execute(
        "SELECT * FROM memory_entries "
        "WHERE owner = ? AND retired_at IS NULL "
        "AND text LIKE '%' || ? || '%' ESCAPE '\\' "
        "ORDER BY created_at DESC, id DESC",
        (owner, _like_escape(query))).fetchall()
    return list(rows)


def list_memories(store: Store, owner: str,
                  include_retired: bool = False) -> list:
    """Newest-first entries for this owner only. Retired entries are
    excluded unless include_retired=True."""
    _ensure_schema(store)
    where = "owner = ?" if include_retired else "owner = ? AND retired_at IS NULL"
    rows = store._db.execute(
        f"SELECT * FROM memory_entries WHERE {where} "
        "ORDER BY created_at DESC, id DESC",
        (owner,)).fetchall()
    return list(rows)


# ---------------------------------------------------------------------------
# Retirement (soft delete — the audit trail survives)
# ---------------------------------------------------------------------------
def retire_memory(store: Store, owner: str, entry_id: int,
                  reason: str = "") -> None:
    """Soft-delete an entry: sets retired_at + retire_reason, the row
    stays for audit. Raises MemoryNotFound (missing id),
    MemoryAccessDenied (another owner's entry), or MemoryRetired
    (already retired)."""
    _ensure_schema(store)
    entry = _entry_or_raise(store, entry_id)
    if entry["owner"] != owner:
        raise MemoryAccessDenied(
            f"memory entry {entry_id} belongs to another owner — "
            "cannot retire it")
    if entry["retired_at"] is not None:
        raise MemoryRetired(f"memory entry {entry_id} is already retired")
    store._db.execute(
        "UPDATE memory_entries SET retired_at = ?, retire_reason = ? "
        "WHERE id = ?",
        (_now(), (reason or "").strip(), entry_id))
    store._db.commit()
