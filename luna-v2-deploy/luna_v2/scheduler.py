"""Scheduler — turns proven one-off missions into recurring habits.

Honest scope, stated up front: Scheduler acts only when tick() is
invoked (today that means the CLI calling it; a system cron may call it
later). It runs no daemon, holds no timer, and promises no wakeups on
its own. A schedule template plus a tick call is what creates the next
mission — nothing fires by itself.

How it works:
- create_schedule() stores a template: a mission title, a list of step
  templates (description + routine/consequential), and a cadence.
- tick() finds every ACTIVE schedule for the owner whose next_run_at is
  at or before now, and creates exactly one real mission per schedule
  through the missions API, so the usual guards still bite: a
  consequential template step lands in the new mission as a
  consequential step that will await approval. That is the approval
  system working as designed, not something the Scheduler bypasses.
- Catch-up is schedule-aligned: next_run_at advances one cadence period
  FROM THE PREVIOUS next_run_at, so a quiet stretch does not drift the
  routine. And it never bursts: at most one mission per schedule per
  tick, no matter how many periods were missed.

Owns its `schedules` table (CREATE TABLE IF NOT EXISTS). Never writes
outside it; makes zero provider calls. All times are UTC ISO strings,
like the rest of the codebase.

Stdlib only.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from luna_v2 import missions as M
from luna_v2.store import Store


class SchedulerError(M.LunaError):
    """Base error for Scheduler problems."""


class ScheduleNotFound(SchedulerError):
    """A schedule id did not exist (or did not belong to that owner)."""


# cadence name -> one period. Kept small and explicit on purpose: "daily"
# and "weekly" cover real habits; hourly or minutely cadences would turn
# tick() into a mission-firing loop, which is the opposite of what a
# quiet routine should be.
CADENCES: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}

STEP_KINDS = (M.ROUTINE, M.CONSEQUENTIAL)

SCHEDULES_SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner          TEXT NOT NULL,
    name           TEXT NOT NULL,
    mission_title  TEXT NOT NULL,
    steps_json     TEXT NOT NULL,
    cadence        TEXT NOT NULL CHECK (cadence IN ('daily', 'weekly')),
    next_run_at    TEXT NOT NULL,
    last_run_at    TEXT NOT NULL DEFAULT '',
    last_mission_id INTEGER,
    active         INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at     TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(SCHEDULES_SCHEMA)
    store._db.commit()


def _coerce_utc(value) -> datetime:
    """Accept an aware/naive datetime or a UTC ISO string; return an
    aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _validate_steps(steps) -> list[dict]:
    if not isinstance(steps, (list, tuple)) or not steps:
        raise SchedulerError("a schedule needs at least one step")
    clean = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            raise SchedulerError(f"step {i} must be a dict "
                                 "{description, kind}")
        desc = (s.get("description") or "").strip()
        kind = s.get("kind")
        if not desc:
            raise SchedulerError(f"step {i} needs a description")
        if kind not in STEP_KINDS:
            raise SchedulerError(
                f"step {i} kind must be one of {STEP_KINDS}, "
                f"got {kind!r}")
        clean.append({"description": desc, "kind": kind})
    return clean


def _schedule_or_raise(store: Store, owner: str,
                       schedule_id: int) -> sqlite3.Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM schedules WHERE id = ? AND owner = ?",
        (schedule_id, owner)).fetchone()
    if row is None:
        raise ScheduleNotFound(
            f"schedule {schedule_id} not found for owner {owner!r}")
    return row


def create_schedule(store: Store, owner: str, name: str, mission_title: str,
                    steps, cadence: str, *, start_at=None) -> int:
    """Store a recurring-mission template. Returns the schedule id.

    next_run_at is `start_at` when given (an aware/naive datetime or a
    UTC ISO string), else now — due immediately on the first tick.
    """
    _ensure_schema(store)
    name = (name or "").strip()
    mission_title = (mission_title or "").strip()
    if not owner:
        raise SchedulerError("owner is required")
    if not name:
        raise SchedulerError("schedule name is required")
    if not mission_title:
        raise SchedulerError("mission title is required")
    if cadence not in CADENCES:
        raise SchedulerError(
            f"cadence must be one of {sorted(CADENCES)}, got {cadence!r}")
    clean_steps = _validate_steps(steps)
    taken = store._db.execute(
        "SELECT id FROM schedules WHERE owner = ? AND name = ? AND active = 1",
        (owner, name)).fetchone()
    if taken is not None:
        raise SchedulerError(
            f"schedule {name!r} is already active for {owner!r} "
            f"(id {taken['id']}) — routines stay unambiguous; deactivate "
            "it first if you want a fresh one")
    next_run = _fmt(_coerce_utc(start_at)) if start_at is not None else _now()
    cur = store._db.execute(
        "INSERT INTO schedules (owner, name, mission_title, steps_json, "
        "cadence, next_run_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner, name, mission_title, json.dumps(clean_steps),
         cadence, next_run, _now()))
    store._db.commit()
    return cur.lastrowid


def tick(store: Store, owner: str, *, now=None) -> list[tuple[int, int]]:
    """Create one mission per due ACTIVE schedule for this owner.

    Returns a list of (schedule_id, mission_id) pairs. At most one
    mission per schedule per tick even if several periods were missed —
    no bursts. next_run_at advances one period from the previous
    next_run_at (schedule-aligned catch-up), so a lull does not drift
    the routine.
    """
    _ensure_schema(store)
    now_dt = _coerce_utc(now) if now is not None else _coerce_utc(_now())
    now_s = _fmt(now_dt)
    due = store._db.execute(
        "SELECT * FROM schedules WHERE owner = ? AND active = 1 "
        "AND next_run_at <= ? ORDER BY id",
        (owner, now_s)).fetchall()
    fired: list[tuple[int, int]] = []
    for sched in due:
        steps = json.loads(sched["steps_json"])
        mission = M.create_mission(
            store, owner, title=sched["mission_title"],
            outcome=(f"Scheduled run of routine '{sched['name']}' "
                     f"({sched['cadence']}); created by scheduler tick "
                     f"at {now_s}."))
        for step in steps:
            M.add_step(store, owner, mission.id,
                       step["description"], step["kind"])
        prev_next = _coerce_utc(sched["next_run_at"])
        next_run = _fmt(prev_next + CADENCES[sched["cadence"]])
        store._db.execute(
            "UPDATE schedules SET last_run_at = ?, last_mission_id = ?, "
            "next_run_at = ? WHERE id = ?",
            (now_s, mission.id, next_run, sched["id"]))
        store._db.commit()
        fired.append((sched["id"], mission.id))
    return fired


def list_schedules(store: Store, owner: str) -> list[sqlite3.Row]:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM schedules WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()


def get_schedule(store: Store, owner: str,
                 schedule_id: int) -> sqlite3.Row:
    return _schedule_or_raise(store, owner, schedule_id)


def set_active(store: Store, owner: str, schedule_id: int,
               active: bool) -> sqlite3.Row:
    """Activate or deactivate a schedule, owner-checked.

    Activating refuses when another active schedule already carries the
    same name for this owner — the name-uniqueness rule has to hold on
    the way back in, not just at creation.
    """
    sched = _schedule_or_raise(store, owner, schedule_id)
    flag = 1 if active else 0
    if flag:
        clash = store._db.execute(
            "SELECT id FROM schedules WHERE owner = ? AND name = ? "
            "AND active = 1 AND id != ?",
            (owner, sched["name"], schedule_id)).fetchone()
        if clash is not None:
            raise SchedulerError(
                f"schedule {sched['name']!r} is already active for "
                f"{owner!r} (id {clash['id']}) — deactivate it first")
    store._db.execute(
        "UPDATE schedules SET active = ? WHERE id = ?",
        (flag, schedule_id))
    store._db.commit()
    return _schedule_or_raise(store, owner, schedule_id)
