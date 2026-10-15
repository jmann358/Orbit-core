"""Trainer: Luna's capability coach.

CHARTER (Jason's directive, 2026-10-14): "New agent, personal trainer,
has the goal of making luna/orbit as capable as muse is. Suggests and
creates plans to be at the top of the food chain."

The Trainer is a COACH, never a judge. Everyone else keeps Luna honest,
safe, working, or staffed — nobody's job is her GROWTH as a capability.
He studies what top-tier systems can do (the reference bar, authored by
Jason/Rowan), names the gap between that and Luna's proven level, and
designs the training plan to close it.

HARD BOUNDARIES (in code, structural tests pin them):
- No grading, no rewards, no retirement. This module never touches the
  grading write paths or the reward/review stores. The grader keeps the
  grades; the Trainer keeps the plans.
- No direct work assignment. Approved plans enter the system through
  Conductor (the `training_plan` backlog kind) like everything else —
  the Trainer never assigns work himself.
- Zero provider calls. Benchmark research routes through Scout /
  Cartographer; drills reuse the gauntlet run-book, the Alchemist's lab,
  and Conductor assignments. Nothing here spends allocation.
- Propose-only. Drafted plans file as deduped Guardian suggestions;
  Jason or Rowan approves. The Trainer never executes a drill himself.
- Evidence only. Luna's current level in a capability area comes ONLY
  from evidence — grades, gauntlet results, mission receipts. Never
  vibes, never self-declared. If no evidence names the level, the level
  is recorded as "unmeasured" — honestly.

Out of scope by charter (stated in the build brief): infrastructure
gaps such as Luna-on-THRONE dispatch are not training gaps. No drill
closes them; the Trainer says so loudly instead of planning around them.
"""
import sqlite3
from datetime import datetime, timezone

from luna_v2 import guardian as GD
from luna_v2 import missions
from luna_v2.store import Store


class TrainerError(missions.LunaError):
    """Refusals from the Trainer's hard boundaries."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS benchmarks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    area          TEXT NOT NULL,              -- capability area slug
    reference_bar TEXT NOT NULL,              -- "top of the food chain",
                                              -- authored by Jason/Rowan
    evidence_level TEXT NOT NULL DEFAULT '',  -- Luna's proven level,
                                              -- from evidence only
    gap_note      TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(owner, area)
);
CREATE TABLE IF NOT EXISTS training_plans (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner          TEXT NOT NULL,
    target         TEXT NOT NULL,              -- capability area being trained
    drills         TEXT NOT NULL DEFAULT '',   -- drill list, free text
    success_measure TEXT NOT NULL DEFAULT '',  -- how "closed" is measured
    status         TEXT NOT NULL DEFAULT 'proposed'
                       CHECK (status IN
                              ('proposed','approved','done','dropped')),
    approved_by    TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_training_plans_status
    ON training_plans(status);
"""

_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_trainer_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._trainer_schema_v = _SCHEMA_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------
def set_benchmark(store: Store, owner: str, area: str, reference_bar: str,
                  evidence_level: str = "", gap_note: str = "",
                  authored_by: str = "") -> sqlite3.Row:
    """Record or update a capability benchmark. The reference bar is
    authored by Jason/Rowan; the level comes from evidence only.

    Deterministic: same (owner, area) always maps to the same row —
    re-setting overwrites, never duplicates. Blank area or reference
    bar is refused. No evidence supplied -> level recorded as
    "unmeasured" rather than invented.
    """
    _ensure_schema(store)
    area = (area or "").strip()
    reference_bar = (reference_bar or "").strip()
    if not area:
        raise TrainerError("refused: the benchmark needs an area")
    if not reference_bar:
        raise TrainerError(
            "refused: the reference bar must be authored by Jason or Rowan")
    level = (evidence_level or "").strip() or "unmeasured"
    cur = store._db.execute(
        "INSERT INTO benchmarks "
        "(owner, area, reference_bar, evidence_level, gap_note, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(owner, area) DO UPDATE SET "
        "reference_bar = excluded.reference_bar, "
        "evidence_level = excluded.evidence_level, "
        "gap_note = excluded.gap_note, "
        "updated_at = excluded.updated_at",
        (owner, area, reference_bar, level, (gap_note or "").strip(),
         _now()))
    store._db.commit()
    rowid = cur.lastrowid or store._db.execute(
        "SELECT id FROM benchmarks WHERE owner = ? AND area = ?",
        (owner, area)).fetchone()["id"]
    return store._db.execute(
        "SELECT * FROM benchmarks WHERE id = ?", (rowid,)).fetchone()


def get_benchmark(store: Store, owner: str, area: str) -> sqlite3.Row | None:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM benchmarks WHERE owner = ? AND area = ?",
        (owner, (area or "").strip())).fetchone()


def list_benchmarks(store: Store, owner: str) -> list[sqlite3.Row]:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM benchmarks WHERE owner = ? ORDER BY area",
        (owner,)).fetchall()


# ---------------------------------------------------------------------------
# Training plans (propose-only)
# ---------------------------------------------------------------------------
def draft_plan(store: Store, owner: str, target: str, drills: str,
               success_measure: str) -> sqlite3.Row:
    """Draft a capability plan. Always lands as 'proposed' — approval is
    Jason's or Rowan's, never the Trainer's. Files one deduped Guardian
    suggestion so the proposal enters the decision queue.
    """
    _ensure_schema(store)
    target = (target or "").strip()
    if not target:
        raise TrainerError("refused: the plan needs a target capability")
    if not (success_measure or "").strip():
        raise TrainerError(
            "refused: a plan needs a written success measure — "
            "a gap is closed only when a re-test shows it closed")
    cur = store._db.execute(
        "INSERT INTO training_plans "
        "(owner, target, drills, success_measure, status, created_at) "
        "VALUES (?, ?, ?, ?, 'proposed', ?)",
        (owner, target, (drills or "").strip(),
         success_measure.strip(), _now()))
    store._db.commit()
    row = store._db.execute(
        "SELECT * FROM training_plans WHERE id = ?",
        (cur.lastrowid,)).fetchone()
    GD.file_suggestion(
        store, owner, "trainer_plan",
        f"Training plan {row['id']} proposed: {target}",
        "info",
        f"The Trainer drafted a capability plan for '{target}'. "
        f"Drills: {row['drills'][:200]}",
        f"training_plans row {row['id']} (status proposed)",
        "Jason or Rowan: approve, drop, or mark done on the plan")
    return row


def decide_plan(store: Store, owner: str, plan_id: int, decision: str,
                decided_by: str) -> sqlite3.Row:
    """Decide a drafted plan: 'approved', 'done', or 'dropped'. The
    decider must be Jason or Rowan — a blank decider or decided_by=
    'trainer' is refused (a coach never approves his own plan).
    """
    _ensure_schema(store)
    by = (decided_by or "").strip()
    if not by:
        raise TrainerError(
            "decide_plan needs a decider name (decided_by)")
    if by.lower() == "trainer":
        raise TrainerError(
            "the Trainer proposes — he cannot approve his own plans; "
            "a Jason or Rowan decision is required")
    if decision not in ("approved", "done", "dropped"):
        raise TrainerError(
            f"decision must be approved/done/dropped, got {decision!r}")
    row = store._db.execute(
        "SELECT * FROM training_plans WHERE owner = ? AND id = ?",
        (owner, plan_id)).fetchone()
    if row is None:
        raise TrainerError(f"no training plan {plan_id}")
    store._db.execute(
        "UPDATE training_plans SET status = ?, approved_by = ? "
        "WHERE id = ?",
        (decision, by if decision == "approved" else row["approved_by"],
         plan_id))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM training_plans WHERE id = ?", (plan_id,)).fetchone()


def list_plans(store: Store, owner: str, status: str = "") -> list[sqlite3.Row]:
    _ensure_schema(store)
    if status:
        if status not in ("proposed", "approved", "done", "dropped"):
            raise TrainerError(f"unknown plan status {status!r}")
        return store._db.execute(
            "SELECT * FROM training_plans WHERE owner = ? AND status = ? "
            "ORDER BY id", (owner, status)).fetchall()
    return store._db.execute(
        "SELECT * FROM training_plans WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()


def gap_summary(store: Store, owner: str) -> list[dict]:
    """Deterministic read of the current gaps: one dict per benchmark.
    Same records -> same summary (a test pins this)."""
    _ensure_schema(store)
    out = []
    for r in list_benchmarks(store, owner):
        out.append({
            "area": r["area"],
            "reference_bar": r["reference_bar"],
            "evidence_level": r["evidence_level"],
            "gap_note": r["gap_note"],
        })
    return out
