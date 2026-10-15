"""Workload — every specialist carries a queue, nobody idles.

Jason's workload directive (2026-10-14 ~19:48 EDT): "force all
workers to work on 10 tasks each, all must do more than they are,
i want constant updates coming out of luna." Rowan's governing
interpretation, Arbiter doctrine applied: 10-deep QUEUES, not 10
simultaneous jobs — a queue is a promise of sourced work, WIP is
limited so the load produces output instead of motion. Anything
beyond real sourced work gets labeled TRAINING at seeding time
(Bundle C's map), never disguised as real work here.

QUEUE LAW (enforced in this module, not by convention):
- MAX 10 OPEN items per specialist. An 11th add is REFUSED.
  Open = queued + active + blocked. Done/failed free the slot.
- MAX 2 ACTIVE items per specialist. A 3rd start is REFUSED.
  Blocked items do not hold an active slot — a blocked job is
  honest about not moving.
- BLOCK requires a blocker note: what is in the way, in words.
  A silent block is refused.
- FAIL requires a failure note: what went wrong, in words.
  A silent failure is refused.
- Every transition is timestamped (created/started/finished +
  updated on every move), so the board can prove motion, not
  assert it.

The board computes per-specialist queued/active/blocked/done
counts from the FULL registry (all thirty-nine) plus the IDLE
list — specialists with zero open items. That list is the
accountability surface: an idle specialist is visible by name.

This module owns bookkeeping only: it records and enforces
queues; it does not assign work (Conductor ticks do), does not
file reports (Bundle B's ops pipeline does), and touches no
other module's tables.

Stdlib only.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from luna_v2 import missions
from luna_v2 import specialists as SP
from luna_v2.store import Store


class WorkloadError(missions.LunaError):
    """Refusals from the queue law."""


MAX_OPEN = 10
MAX_ACTIVE = 2
OPEN_STATUSES = ("queued", "active", "blocked")
STATUSES = OPEN_STATUSES + ("done", "failed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    specialist  TEXT NOT NULL,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    priority    INTEGER NOT NULL DEFAULT 5,
    status      TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','active','blocked',
                                  'done','failed')),
    blocker     TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    mission_id  INTEGER,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_work_queue_owner
    ON work_queue(owner, specialist, status);
"""
_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_workload_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._workload_schema_v = _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _check_specialist(specialist: str) -> str:
    name = (specialist or "").strip().lower()
    if name not in SP.SPECIALISTS:
        raise WorkloadError(
            f"unknown specialist {specialist!r} — the queue only "
            f"carries registered specialists")
    return name


def _get(store: Store, owner: str, item_id: int) -> sqlite3.Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM work_queue WHERE id = ? AND owner = ?",
        (item_id, owner)).fetchone()
    if row is None:
        raise WorkloadError(f"no work item {item_id}")
    return row


def _count(store: Store, owner: str, specialist: str,
           statuses: tuple) -> int:
    marks = ",".join("?" for _ in statuses)
    return store._db.execute(
        f"SELECT COUNT(*) AS n FROM work_queue WHERE owner = ? "
        f"AND specialist = ? AND status IN ({marks})",
        (owner, specialist, *statuses)).fetchone()["n"]


def _set(store: Store, owner: str, item_id: int, **fields) -> sqlite3.Row:
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    store._db.execute(
        f"UPDATE work_queue SET {cols} WHERE id = ? AND owner = ?",
        (*fields.values(), item_id, owner))
    store._db.commit()
    return _get(store, owner, item_id)


def _pulse(store: Store, owner: str, kind: str, row: sqlite3.Row,
           summary: str) -> None:
    """Emit the matching ops pulse for a transition (Bundle B).
    Lazy import: the queue law never depends on the ops module
    being importable, and ops never imports workload."""
    from luna_v2 import ops as OPS
    OPS.emit_pulse(store, owner, kind, row["specialist"], summary,
                   ref=f"work-item:{row['id']}")


# ---------------------------------------------------------------------------
# Queue law: add / list
# ---------------------------------------------------------------------------
def add_item(store: Store, owner: str, specialist: str, title: str,
             *, source: str = "", priority: int = 5,
             mission_id: int | None = None) -> sqlite3.Row:
    """Queue one item. Refused when the specialist already carries
    MAX_OPEN open items — the queue is a promise, not a pile."""
    _ensure_schema(store)
    name = _check_specialist(specialist)
    if not (title or "").strip():
        raise WorkloadError("a work item needs a title")
    open_n = _count(store, owner, name, OPEN_STATUSES)
    if open_n >= MAX_OPEN:
        raise WorkloadError(
            f"{name} already carries {open_n} open item(s) — the "
            f"queue law caps a queue at {MAX_OPEN} open; finish or "
            f"fail something before piling on more")
    now = _now()
    cur = store._db.execute(
        "INSERT INTO work_queue (owner, specialist, title, source, "
        "priority, mission_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (owner, name, title.strip(), (source or "").strip(),
         int(priority), mission_id, now, now))
    store._db.commit()
    return _get(store, owner, cur.lastrowid)


def list_items(store: Store, owner: str, specialist: str = "",
               status: str = "") -> list:
    """Queue items, optionally filtered; highest priority first
    (lowest number), then oldest first."""
    _ensure_schema(store)
    q = "SELECT * FROM work_queue WHERE owner = ?"
    args: list = [owner]
    if specialist:
        q += " AND specialist = ?"
        args.append(_check_specialist(specialist))
    if status:
        if status not in STATUSES:
            raise WorkloadError(f"status must be one of {STATUSES}")
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY priority, id"
    return store._db.execute(q, args).fetchall()


# ---------------------------------------------------------------------------
# Transitions (all timestamped via _set)
# ---------------------------------------------------------------------------
def start_item(store: Store, owner: str, item_id: int) -> sqlite3.Row:
    """queued → active. Refused when the specialist already runs
    MAX_ACTIVE items — WIP limits keep the load honest."""
    row = _get(store, owner, item_id)
    if row["status"] != "queued":
        raise WorkloadError(
            f"work item {item_id} is {row['status']}, not queued — "
            f"only a queued item can start (unblock a blocked item "
            f"first)")
    active_n = _count(store, owner, row["specialist"], ("active",))
    if active_n >= MAX_ACTIVE:
        raise WorkloadError(
            f"{row['specialist']} already has {active_n} active "
            f"item(s) — the WIP limit is {MAX_ACTIVE}; finish or "
            f"block one before starting another")
    out = _set(store, owner, item_id, status="active",
               started_at=_now())
    _pulse(store, owner, "started", out,
           f"started work item {item_id}: {out['title']}")
    return out


def block_item(store: Store, owner: str, item_id: int,
               blocker: str) -> sqlite3.Row:
    """active → blocked. The blocker note is REQUIRED — a silent
    block is refused, because 'blocked' without a reason is how
    work goes to die quietly."""
    if not (blocker or "").strip():
        raise WorkloadError(
            "blocking requires a blocker note — what is in the "
            "way, in plain words")
    row = _get(store, owner, item_id)
    if row["status"] != "active":
        raise WorkloadError(
            f"work item {item_id} is {row['status']}, not active — "
            f"only an active item can block")
    out = _set(store, owner, item_id, status="blocked",
               blocker=blocker.strip())
    _pulse(store, owner, "blocked", out,
           f"work item {item_id} blocked: {blocker.strip()}")
    return out


def unblock_item(store: Store, owner: str, item_id: int) -> sqlite3.Row:
    """blocked → queued, blocker cleared. The item must be started
    again explicitly — unblocking never silently resumes work."""
    row = _get(store, owner, item_id)
    if row["status"] != "blocked":
        raise WorkloadError(
            f"work item {item_id} is {row['status']}, not blocked")
    return _set(store, owner, item_id, status="queued", blocker="")


def complete_item(store: Store, owner: str, item_id: int) -> sqlite3.Row:
    """queued|active → done, finished_at stamped. A blocked item
    must be unblocked first — blocked means it cannot proceed."""
    row = _get(store, owner, item_id)
    if row["status"] not in ("queued", "active"):
        raise WorkloadError(
            f"work item {item_id} is {row['status']} — it cannot "
            f"be completed from there"
            + (" (unblock it first)" if row["status"] == "blocked"
               else ""))
    out = _set(store, owner, item_id, status="done",
               finished_at=_now())
    _pulse(store, owner, "done", out,
           f"work item {item_id} done: {out['title']}")
    return out


def fail_item(store: Store, owner: str, item_id: int,
              note: str) -> sqlite3.Row:
    """Any open status → failed. The failure note is REQUIRED —
    what went wrong, in plain words. A silent failure is refused."""
    if not (note or "").strip():
        raise WorkloadError(
            "failing an item requires a failure note — what went "
            "wrong, in plain words")
    row = _get(store, owner, item_id)
    if row["status"] not in OPEN_STATUSES:
        raise WorkloadError(
            f"work item {item_id} is already {row['status']}")
    out = _set(store, owner, item_id, status="failed",
               note=note.strip(), finished_at=_now())
    _pulse(store, owner, "failed", out,
           f"work item {item_id} failed: {note.strip()}")
    return out


# ---------------------------------------------------------------------------
# Board math
# ---------------------------------------------------------------------------
def board(store: Store, owner: str) -> dict:
    """Per-specialist queue counts over the FULL registry, plus
    totals and the IDLE list (zero open items). Every registered
    specialist appears, carrying a queue or named idle."""
    _ensure_schema(store)
    rows = store._db.execute(
        "SELECT specialist, status, COUNT(*) AS n FROM work_queue "
        "WHERE owner = ? GROUP BY specialist, status",
        (owner,)).fetchall()
    counts: dict = {}
    for r in rows:
        counts.setdefault(r["specialist"], {})[r["status"]] = r["n"]
    specialists = []
    totals = {s: 0 for s in STATUSES}
    idle = []
    for name in sorted(SP.SPECIALISTS):
        c = counts.get(name, {})
        entry = {"specialist": name}
        for s in STATUSES:
            entry[s] = c.get(s, 0)
            totals[s] += entry[s]
        entry["open"] = sum(entry[s] for s in OPEN_STATUSES)
        specialists.append(entry)
        if entry["open"] == 0:
            idle.append(name)
    totals["open"] = sum(totals[s] for s in OPEN_STATUSES)
    return {"owner": owner, "specialists": specialists,
            "totals": totals, "idle": idle}


def summary_line(store: Store, owner: str) -> str:
    """One-line workload summary for status surfaces (Conductor)."""
    b = board(store, owner)
    t = b["totals"]
    return (f"workload: {t['open']} open ({t['queued']} queued · "
            f"{t['active']} active · {t['blocked']} blocked) · "
            f"{t['done']} done · {t['failed']} failed · "
            f"{len(b['idle'])} idle specialist(s)")
