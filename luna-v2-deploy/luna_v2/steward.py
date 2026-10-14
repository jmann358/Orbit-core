"""Steward: Luna's personal-projects owner (the house steward).

CHARTER (from Jason's Christmas-list organizing, 2026-10-14): the 30
specialists cover every MECHANIC of personal-life logistics (Scheduler
ticks, Herald briefs, Archivist's year-over-year memory, Quartermaster's
envelopes, Scout's research, Conductor's anti-idle), but nobody OWNED a
personal project end-to-end or ran the chase-the-human loop. Steward is
the human-facing half of the court's operations: he keeps Jason's
personal projects warm across months, maintains the outstanding-questions
queue, and escalates the nudge as the deadline's ladder steepens.

HARD BOUNDARIES (Jason-approved, filed in Steward's probation scope):
- Projects exist only with a named approver. Jason-approved projects
  only; create_project refuses blank approvers, no exceptions.
- Steward executes NOTHING himself. Execution is handed to Conductor /
  Herald / Scout / Quartermaster etc.; projects carry a free-text
  `handoff` field naming the executor. Steward makes zero provider
  calls — he plans, tracks, and nudges.
- Steward has NO channel to Jason. nudge_check PREPARES nudges as
  deduped Guardian suggestions ('steward_nudge', info); Herald or Rowan
  carries them. Steward never sends anything himself.
- No butler-scope creep: personal projects only (kind is locked to
  'personal'); the probation watch item is Steward swelling into a
  generic everything-butler.
"""
import sqlite3
from datetime import date, datetime

from luna_v2 import guardian as GD
from luna_v2 import missions
from luna_v2.store import Store


class StewardError(missions.LunaError):
    """Refusals from the Steward's hard boundaries."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    title       TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'personal'
                    CHECK (kind IN ('personal')),
    deadline    TEXT NOT NULL,          -- ISO date YYYY-MM-DD
    status      TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','done','parked')),
    approved_by TEXT NOT NULL,
    mission_id  INTEGER,                -- link into Luna's mission system
    handoff     TEXT NOT NULL DEFAULT '',  -- who executes (free text)
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS project_questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    question    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','answered','dropped')),
    asked_count INTEGER NOT NULL DEFAULT 0,
    last_asked_at TEXT,                 -- ISO date
    answer_note TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_project_questions_pid
    ON project_questions(project_id);
"""

_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_steward_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._steward_schema_v = _SCHEMA_VERSION


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _valid_date(value: str) -> str:
    """Validate an ISO date (YYYY-MM-DD); return it unchanged."""
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError):
        raise StewardError(
            f"deadline must be an ISO date (YYYY-MM-DD), got {value!r}")
    return value


def get_project(store: Store, owner: str, project_id: int) -> sqlite3.Row:
    """Fetch one project (raises StewardError when unknown)."""
    _ensure_schema(store)
    return _get_project(store, owner, project_id)


def _get_project(store: Store, owner: str, project_id: int) -> sqlite3.Row:
    row = store._db.execute(
        "SELECT * FROM projects WHERE owner = ? AND id = ?",
        (owner, project_id)).fetchone()
    if row is None:
        raise StewardError(f"no project {project_id}")
    return row


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
def create_project(store: Store, owner: str, title: str, deadline: str,
                   approved_by: str, mission_id=None, handoff: str = "",
                   note: str = "", today: date | None = None) -> sqlite3.Row:
    """Register a personal project. approved_by is mandatory (Jason-approved
    projects only) and the deadline must not be in the past."""
    _ensure_schema(store)
    if not approved_by or not approved_by.strip():
        raise StewardError(
            "refused: a personal project needs a named approver "
            "(Jason-approved projects only)")
    if not title or not title.strip():
        raise StewardError("refused: the project needs a title")
    day = _valid_date(deadline)
    today = today or date.today()
    if date.fromisoformat(day) < today:
        raise StewardError(
            f"refused: deadline {day} is before today {today.isoformat()}")
    cur = store._db.execute(
        "INSERT INTO projects (owner, title, kind, deadline, status, "
        "approved_by, mission_id, handoff, note, created_at) "
        "VALUES (?, ?, 'personal', ?, 'active', ?, ?, ?, ?, ?)",
        (owner, title.strip(), day, approved_by.strip(), mission_id,
         handoff.strip(), note, _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM projects WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_projects(store: Store, owner: str, status: str = "active") \
        -> list[sqlite3.Row]:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM projects WHERE owner = ? AND status = ? "
        "ORDER BY deadline",
        (owner, status)).fetchall()


def set_status(store: Store, owner: str, project_id: int, status: str) \
        -> sqlite3.Row:
    _ensure_schema(store)
    if status not in ("active", "done", "parked"):
        raise StewardError(f"status must be active/done/parked, got {status!r}")
    _get_project(store, owner, project_id)
    store._db.execute(
        "UPDATE projects SET status = ? WHERE owner = ? AND id = ?",
        (status, owner, project_id))
    store._db.commit()
    return _get_project(store, owner, project_id)


def set_handoff(store: Store, owner: str, project_id: int, handoff: str) \
        -> sqlite3.Row:
    """Record who executes the project (free text). Steward still executes
    nothing himself; this is the routing note."""
    _ensure_schema(store)
    _get_project(store, owner, project_id)
    store._db.execute(
        "UPDATE projects SET handoff = ? WHERE owner = ? AND id = ?",
        (handoff.strip(), owner, project_id))
    store._db.commit()
    return _get_project(store, owner, project_id)


# ---------------------------------------------------------------------------
# The ladder: deadline-driven urgency tiers
# ---------------------------------------------------------------------------
# (tier, minimum days_left for the tier, cadence label, nudge gap in days)
_TIERS = [
    ("setup", 46, "monthly glance", 30),
    ("weekly", 15, "weekly brief", 7),
    ("twice_weekly", 8, "twice-weekly brief", 3),
    ("daily", 1, "daily check", 1),
    ("final", 0, "final verification", 1),
]


def ladder_status(project: sqlite3.Row, today: date | None = None) -> dict:
    """Deadline-driven urgency tier. `today` is injected (defaults to the
    real date) so the math is deterministic and testable."""
    today = today or date.today()
    days_left = (date.fromisoformat(project["deadline"]) - today).days
    if days_left < 0:
        return {"tier": "closed_window",
                "cadence": "window closed — post-deadline review",
                "days_left": days_left, "nudge_gap_days": None}
    for tier, minimum, cadence, gap in _TIERS:
        if days_left >= minimum:
            return {"tier": tier, "cadence": cadence,
                    "days_left": days_left, "nudge_gap_days": gap}
    # days_left is 0 here only (handled by "final" above); keep total.
    return {"tier": "final", "cadence": "final verification",
            "days_left": days_left, "nudge_gap_days": 1}


# ---------------------------------------------------------------------------
# The question queue (the chase-the-human loop)
# ---------------------------------------------------------------------------
def add_question(store: Store, owner: str, project_id: int, question: str) \
        -> sqlite3.Row:
    _ensure_schema(store)
    _get_project(store, owner, project_id)
    if not question or not question.strip():
        raise StewardError("refused: the question cannot be blank")
    cur = store._db.execute(
        "INSERT INTO project_questions (owner, project_id, question) "
        "VALUES (?, ?, ?)",
        (owner, project_id, question.strip()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM project_questions WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_questions(store: Store, owner: str, project_id: int,
                   status: str = "open") -> list[sqlite3.Row]:
    _ensure_schema(store)
    _get_project(store, owner, project_id)
    return store._db.execute(
        "SELECT * FROM project_questions "
        "WHERE owner = ? AND project_id = ? AND status = ? ORDER BY id",
        (owner, project_id, status)).fetchall()


def answer_question(store: Store, owner: str, question_id: int,
                    answer_note: str) -> sqlite3.Row:
    _ensure_schema(store)
    if not answer_note or not answer_note.strip():
        raise StewardError("refused: the answer note cannot be blank")
    row = store._db.execute(
        "SELECT * FROM project_questions WHERE owner = ? AND id = ?",
        (owner, question_id)).fetchone()
    if row is None:
        raise StewardError(f"no question {question_id}")
    store._db.execute(
        "UPDATE project_questions SET status = 'answered', "
        "answer_note = ? WHERE owner = ? AND id = ?",
        (answer_note.strip(), owner, question_id))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM project_questions WHERE id = ?",
        (question_id,)).fetchone()


def drop_question(store: Store, owner: str, question_id: int) -> sqlite3.Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM project_questions WHERE owner = ? AND id = ?",
        (owner, question_id)).fetchone()
    if row is None:
        raise StewardError(f"no question {question_id}")
    store._db.execute(
        "UPDATE project_questions SET status = 'dropped' "
        "WHERE owner = ? AND id = ?",
        (owner, question_id))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM project_questions WHERE id = ?",
        (question_id,)).fetchone()


def _question_is_due(question: sqlite3.Row, tier: dict,
                     today: date) -> bool:
    """An open question is due when the tier's cadence says so."""
    gap = tier["nudge_gap_days"]
    if gap is None:
        return False
    last = question["last_asked_at"]
    if last is None:
        return True  # never asked — always due
    asked = (today - date.fromisoformat(last)).days
    return asked >= gap


def due_questions(store: Store, owner: str, project_id: int,
                  today: date | None = None) -> tuple[dict, list]:
    """(ladder tier dict, due open questions) for one project."""
    today = today or date.today()
    _ensure_schema(store)
    project = _get_project(store, owner, project_id)
    tier = ladder_status(project, today)
    due = [q for q in list_questions(store, owner, project_id, "open")
           if _question_is_due(q, tier, today)]
    return tier, due


# ---------------------------------------------------------------------------
# Nudge loop: prepare (never send) the nudges
# ---------------------------------------------------------------------------
def nudge_check(store: Store, owner: str,
                today: date | None = None) -> dict:
    """Across active projects, file ONE deduped Guardian suggestion per
    project that has due open questions. asked_count/last_asked_at update
    ONLY when a nudge is actually filed. Returns a small report.

    Steward PREPARES nudges — he has no channel to Jason and sends
    nothing. Herald or Rowan carries them.
    """
    today = today or date.today()
    _ensure_schema(store)
    nudged_projects = 0
    filed = 0
    projects = list_projects(store, owner, "active")
    for project in projects:
        tier, due = due_questions(store, owner, project["id"], today)
        if not due:
            continue
        observation = (
            f"Personal project '{project['title']}' is in the "
            f"{tier['tier']} tier ({tier['days_left']} day(s) to "
            f"{project['deadline']}; cadence: {tier['cadence']}) with "
            f"{len(due)} open question(s) due for Jason. "
            f"Carry these in the next briefing: " +
            "; ".join(f"Q{q['id']}: {q['question']}" for q in due))
        row, created = GD._file_one(
            store, owner, "steward_nudge",
            subject=f"project:{project['id']}",
            severity="info", observation=observation,
            evidence=(f"project {project['id']} '{project['title']}', "
                      f"deadline {project['deadline']}, tier "
                      f"{tier['tier']}, {len(due)} question(s) due"),
            proposed_action=(
                f"Herald: carry the {len(due)} open question(s) for "
                f"'{project['title']}' in the next {tier['cadence']}; "
                f"Rowan: confirm the answers landed."))
        if created:
            filed += 1
            nudged_projects += 1
            today_iso = today.isoformat()
            for q in due:
                store._db.execute(
                    "UPDATE project_questions SET asked_count = asked_count + 1, "
                    "last_asked_at = ? WHERE id = ?",
                    (today_iso, q["id"]))
            store._db.commit()
    return {"active_projects": len(projects), "nudged_projects": nudged_projects,
            "suggestions_filed": filed}
