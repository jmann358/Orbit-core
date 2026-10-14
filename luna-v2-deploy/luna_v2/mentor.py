"""Mentor: the specialist who trains the team.

Jason's direction (2026-10-13): Luna grows a team of specialists; Mentor
is the one who keeps them honest. It grades specialists' runs with
deterministic, inspectable signals (status + result + error on the run
record — never a model call, never a feeling), aggregates weak patterns
per specialist, and files improvement drafts into Guardian's inbox for
Rowan to approve.

Deliberate rules:
- Mentor reads specialist_runs. Its only writes are its own
  mentor_reviews rows, and — through Guardian's public API — new
  guardian_suggestions. It never UPDATEs a specialist_runs row, a
  profile, or anything else. It advises; Rowan decides.
- Grading is deterministic: same records, same grades, every time.
- Filing leans on Guardian's open-suggestion dedupe (one open
  mentor_review suggestion per specialist), so re-running a draft
  files no duplicates.

Review-and-retire (Jason's 2026-10-14 direction): grades persist into
mentor_grades; consistently weak specialists open review_cases with a
recommendation (train/restrict/retire) and a redelegation draft. But
Mentor only RECOMMENDS — decide_case refuses decided_by='mentor'
(blank or missing deciders are refused too). Only Jason or Rowan may
decide, and retirement/restriction land as specialist_status rows,
never registry edits. Earned rewards are never touched: the only
"teeth" are lower grades, fewer FUTURE rewards (resource grants pause
while a case is open), and Jason's decision.

Stdlib only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2 import builder as B
from luna_v2 import specialists as SP
from luna_v2.store import Store


class MentorError(M.LunaError):
    """Base error for Mentor."""


GRADES = ("strong", "ok", "weak")

# Review thresholds — named constants, Jason's 2026-10-14 direction.
REVIEW_MIN_GRADES = 5    # persisted grades a specialist needs before review
REVIEW_WINDOW = 10       # last N persisted grades examined
REVIEW_WEAK_TRIGGER = 3  # >= this many weak in the window opens a case
RESTRICT_WEAK_SHARE = 0.5  # weak share >= this -> 'restrict'
RETIRE_WEAK_SHARE = 0.8    # weak share >= this -> 'retire' (else 'train')

MENTOR_REVIEWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS mentor_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    runs_graded     INTEGER NOT NULL,
    grades_json     TEXT NOT NULL DEFAULT '[]',
    suggestions_filed INTEGER NOT NULL DEFAULT 0
);
"""

MENTOR_GRADES_SCHEMA = """
CREATE TABLE IF NOT EXISTS mentor_grades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    specialist  TEXT NOT NULL,
    run_source  TEXT NOT NULL,          -- 'specialist_runs' | 'builder_runs'
    run_id      INTEGER NOT NULL,
    run_created_at TEXT NOT NULL DEFAULT '',  -- the RUN's own timestamp:
                                  -- history is ordered by run recency,
                                  -- never by grade-row insertion order
    grade       TEXT NOT NULL CHECK (grade IN ('strong','ok','weak')),
    reason      TEXT NOT NULL DEFAULT '',
    graded_at   TEXT NOT NULL,
    UNIQUE (owner, run_source, run_id)
);
"""

REVIEW_CASES_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    specialist      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','decided')),
    trigger_summary TEXT NOT NULL DEFAULT '',
    recommendation  TEXT NOT NULL
                    CHECK (recommendation IN ('train','restrict','retire')),
    redelegation_plan TEXT NOT NULL DEFAULT '',
    decided_by      TEXT,
    decision        TEXT,
    decided_at      TEXT,
    created_at      TEXT NOT NULL
);
"""

DECISIONS = ("train", "restrict", "retire", "dismiss")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(MENTOR_REVIEWS_SCHEMA)
    store._db.execute(MENTOR_GRADES_SCHEMA)
    store._db.execute(REVIEW_CASES_SCHEMA)
    store._db.commit()


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
def _grade_run(row) -> dict:
    """One deterministic grade from the run record's own fields."""
    status = row["status"]
    result = row["result"] or ""
    error = row["error"] or ""
    mission_attributed = row["mission_id"] is not None

    if status == "failed":
        first_line = error.splitlines()[0] if error.splitlines() else "(no error recorded)"
        reason = f"failed: {first_line}"
        grade = "weak"
    elif status == "started":
        reason = "run never finished"
        grade = "weak"
    elif status == "done" and not result.strip():
        reason = "completed with an empty result"
        grade = "weak"
    elif status == "done" and error.strip():
        reason = f"completed with a partial issue: {error.splitlines()[0]}"
        grade = "ok"
    else:  # done with a non-empty result and no error
        reason = "completed cleanly"
        grade = "strong"

    return {
        "run_id": row["id"],
        "run_source": row["run_source"],
        "run_created_at": row["created_at"],
        "specialist": row["specialist"],
        "grade": grade,
        "reason": reason,
        "mission_attributed": mission_attributed,
    }


def grade_runs(store: Store, owner: str, *, limit: int = 20) -> list[dict]:
    """Grade the owner's most recent specialist runs (newest first).

    Read-only. Builder keeps its own run table (builder_runs) rather
    than specialist_runs, so Builder runs are mapped into the same
    shape here: specialist='builder', result is the task with the test
    exit code, and a failed build's error is the failing test tail.
    Done builds (tests exited 0) grade strong; failed builds grade
    weak, with the first failing line as the reason.

    Read-only: SELECTs only, writes nothing.
    """
    SP._ensure_schema(store)
    B._ensure_schema(store)
    rows = store._db.execute(
        "SELECT id, run_source, owner, mission_id, specialist, status, "
        "result, error, created_at FROM ("
        "SELECT id, 'specialist_runs' AS run_source, owner, mission_id, "
        "specialist, status, result, error, created_at "
        "FROM specialist_runs WHERE owner = ? "
        "UNION ALL "
        "SELECT id, 'builder_runs' AS run_source, owner, mission_id, "
        "'builder' AS specialist, status, "
        "'task: ' || task || ' (tests exit ' || test_exit_code || ')' "
        "AS result, "
        "CASE WHEN status = 'failed' THEN test_tail ELSE '' END AS error, "
        "created_at FROM builder_runs WHERE owner = ?) "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        (owner, owner, limit)).fetchall()
    return [_grade_run(r) for r in rows]


# ---------------------------------------------------------------------------
# Improvement drafts -> Guardian's inbox
# ---------------------------------------------------------------------------
def _draft_text(specialist: str, weak_runs: list[dict],
                window_size: int) -> tuple[str, str, str]:
    """Returns (observation, evidence, proposed_action)."""
    n_weak = len(weak_runs)
    observation = (
        f"mentor: {n_weak} of the last {window_size} {specialist} "
        f"run{'s' if window_size != 1 else ''} graded weak")
    evidence_lines = [
        f"run {g['run_id']}: {g['reason']}" for g in weak_runs]
    evidence = ("weak runs:\n" + "\n".join(evidence_lines))
    # A reviewable draft per weak pattern; Mentor never applies anything.
    proposed_action = (
        f"Draft for Rowan: review {specialist}'s weak run records for a "
        f"pattern. Suggested reviewables: "
        f"1) re-read the cited reasons on the run rows; "
        f"2) if failures look transient (fetch/network), consider adding "
        f"a retry-once to the {specialist} runner; "
        f"3) if results are empty, tighten the task prompt. "
        f"Mentor never applies changes itself — approve any edit to the "
        f"{specialist} profile or runner before it ships.")
    return observation, evidence, proposed_action


def draft_improvements(store: Store, owner: str, *,
                       limit: int = 20) -> dict:
    """Grade the recent window and file ONE Guardian suggestion per
    specialist that has at least one weak run.

    Severity: 'warning' when that specialist's window is majority-weak
    (more weak than half the window), otherwise 'info'. Filing goes
    through Guardian's dedupe, so an already-open mentor_review
    suggestion for a specialist is returned, never refiled.

    Records a mentor_reviews row (its only direct write). Returns
    {"runs_graded", "per_specialist", "suggestions_filed"}.
    """
    grades = grade_runs(store, owner, limit=limit)
    _ensure_schema(store)

    # aggregate per specialist over the graded window
    per_specialist: dict[str, dict] = {}
    for g in grades:
        agg = per_specialist.setdefault(
            g["specialist"],
            {"graded": 0, "weak": 0, "strong": 0, "ok": 0,
             "weak_runs": []})
        agg["graded"] += 1
        agg[g["grade"]] += 1
        if g["grade"] == "weak":
            agg["weak_runs"].append(g)

    suggestions_filed = 0
    for specialist, agg in per_specialist.items():
        if not agg["weak_runs"]:
            continue
        severity = "warning" if agg["weak"] > agg["graded"] / 2 else "info"
        observation, evidence, proposed_action = _draft_text(
            specialist, agg["weak_runs"], agg["graded"])
        before = len(G.inbox(store, owner))
        G.file_suggestion(
            store, owner,
            check_name="mentor_review",
            subject=specialist,
            severity=severity,
            observation=observation,
            evidence=evidence,
            proposed_action=proposed_action)
        after = len(G.inbox(store, owner))
        if after > before:
            suggestions_filed += 1

    review = {
        "runs_graded": len(grades),
        "per_specialist": {
            name: {k: v for k, v in agg.items() if k != "weak_runs"}
            for name, agg in per_specialist.items()
        },
        "suggestions_filed": suggestions_filed,
    }
    store._db.execute(
        "INSERT INTO mentor_reviews (owner, created_at, runs_graded, "
        "grades_json, suggestions_filed) VALUES (?, ?, ?, ?, ?)",
        (owner, _now(), len(grades), json.dumps(grades),
         suggestions_filed))
    store._db.commit()
    return review


# ---------------------------------------------------------------------------
# Persistent grades
# ---------------------------------------------------------------------------
def persist_grades(store: Store, owner: str, *, limit: int = 50) -> dict:
    """Grade recent runs and persist each run's grade exactly once.

    Idempotent: re-running adds nothing (UNIQUE on
    owner/run_source/run_id). Returns {"graded", "persisted_new"}.
    """
    _ensure_schema(store)
    grades = grade_runs(store, owner, limit=limit)
    added = 0
    for g in grades:
        cur = store._db.execute(
            "INSERT OR IGNORE INTO mentor_grades (owner, specialist, "
            "run_source, run_id, run_created_at, grade, reason, "
            "graded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (owner, g["specialist"], g["run_source"], g["run_id"],
             g["run_created_at"], g["grade"], g["reason"], _now()))
        if cur.rowcount:
            added += 1
    store._db.commit()
    return {"graded": len(grades), "persisted_new": added}


def grade_history(store: Store, owner: str,
                  specialist: str | None = None) -> list[dict]:
    """Persisted grades, newest RUN first; optionally for one
    specialist. Ordered by the run's own timestamp (ties broken
    deterministically), never by grade-row insertion order."""
    _ensure_schema(store)
    order = ("ORDER BY run_created_at DESC, run_source DESC, "
             "run_id DESC")
    if specialist is not None:
        rows = store._db.execute(
            "SELECT * FROM mentor_grades WHERE owner = ? AND "
            f"specialist = ? {order}",
            (owner, specialist)).fetchall()
    else:
        rows = store._db.execute(
            f"SELECT * FROM mentor_grades WHERE owner = ? {order}",
            (owner,)).fetchall()
    return [dict(r) for r in rows]


def grade_summary(store: Store, owner: str, specialist: str,
                  last_n: int = REVIEW_WINDOW) -> dict:
    """Grade counts over the last N persisted grades of a specialist."""
    rows = grade_history(store, owner, specialist)[:last_n]
    counts = {"strong": 0, "ok": 0, "weak": 0}
    for r in rows:
        counts[r["grade"]] += 1
    return {"specialist": specialist, "last_n": len(rows),
            "counts": counts}


# ---------------------------------------------------------------------------
# Review cases
# ---------------------------------------------------------------------------
def open_case_for(store: Store, owner: str,
                  specialist: str) -> dict | None:
    """The specialist's open review case, if any."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM review_cases WHERE owner = ? AND specialist = ? "
        "AND status = 'open' ORDER BY id DESC LIMIT 1",
        (owner, specialist)).fetchone()
    return dict(row) if row is not None else None


def list_cases(store: Store, owner: str,
               status: str | None = None) -> list[dict]:
    """All review cases, newest first; optionally filtered by status."""
    _ensure_schema(store)
    if status is not None:
        rows = store._db.execute(
            "SELECT * FROM review_cases WHERE owner = ? AND status = ? "
            "ORDER BY id DESC", (owner, status)).fetchall()
    else:
        rows = store._db.execute(
            "SELECT * FROM review_cases WHERE owner = ? ORDER BY id DESC",
            (owner,)).fetchall()
    return [dict(r) for r in rows]


def evaluate_reviews(store: Store, owner: str) -> dict:
    """Open review cases for consistently weak specialists.

    Persist grades first (idempotent), then for each specialist with
    at least REVIEW_MIN_GRADES persisted grades: if at least
    REVIEW_WEAK_TRIGGER of their last REVIEW_WINDOW grades are weak
    and no case is already open, open one. The recommendation follows
    the weak share: >= RETIRE_WEAK_SHARE -> 'retire',
    >= RESTRICT_WEAK_SHARE -> 'restrict', else 'train'. Opening a
    case files ONE Guardian suggestion (check_name='mentor_review_case',
    severity warning) and saves a redelegation draft on the case.
    Nothing is ever auto-decided. Returns {"cases_opened": [ids]}.
    """
    persist_grades(store, owner)
    _ensure_schema(store)
    owners_specialists = store._db.execute(
        "SELECT DISTINCT specialist FROM mentor_grades WHERE owner = ?",
        (owner,)).fetchall()
    opened = []
    for (specialist,) in owners_specialists:
        if open_case_for(store, owner, specialist) is not None:
            continue
        summary = grade_summary(store, owner, specialist,
                                last_n=REVIEW_WINDOW)
        if summary["last_n"] < REVIEW_MIN_GRADES:
            continue
        weak = summary["counts"]["weak"]
        if weak < REVIEW_WEAK_TRIGGER:
            continue
        share = weak / summary["last_n"]
        if share >= RETIRE_WEAK_SHARE:
            recommendation = "retire"
        elif share >= RESTRICT_WEAK_SHARE:
            recommendation = "restrict"
        else:
            recommendation = "train"
        trigger = (f"{weak} of the last {summary['last_n']} persisted "
                   f"grades weak ({share:.0%})")
        plan = draft_redelegation(store, owner, specialist)
        cid = store._db.execute(
            "INSERT INTO review_cases (owner, specialist, status, "
            "trigger_summary, recommendation, redelegation_plan, "
            "created_at) VALUES (?, ?, 'open', ?, ?, ?, ?)",
            (owner, specialist, trigger, recommendation, plan,
             _now())).lastrowid
        G.file_suggestion(
            store, owner,
            check_name="mentor_review_case",
            subject=specialist,
            severity="warning",
            observation=(f"mentor: review case {cid} opened for "
                         f"{specialist} — {trigger}; recommendation: "
                         f"{recommendation}"),
            evidence=(f"trigger: {trigger}\n\nredelegation draft:\n{plan}"),
            proposed_action=(
                f"For Jason/Rowan: review the evidence and decide "
                f"(mentor decide {cid} --decision <train|restrict|retire|"
                f"dismiss> --by <your name>). Training comes before "
                f"removal; earned rewards are never revoked — poor work "
                f"only throttles future rewards."))
        store._db.commit()
        opened.append(cid)
    return {"cases_opened": opened}


def _tokenize(text: str) -> set[str]:
    import re as _re
    return set(_re.findall(r"[a-z]+", text.lower()))


def _tool_overlap(duty: str, profile: SP.SpecialistProfile) -> int:
    """Deterministic overlap score: token intersection between the
    duty and another profile's tool names, plus its purpose keywords."""
    duty_tokens = _tokenize(duty.replace("-", " ").replace("_", " "))
    best = 0
    for tool in profile.tools:
        best = max(best, len(duty_tokens & _tokenize(
            tool.replace("-", " ").replace("_", " "))))
    return best + len(duty_tokens & _tokenize(profile.purpose))


def draft_redelegation(store: Store, owner: str, specialist: str) -> str:
    """Draft (never apply) where a specialist's duties would go.

    Each declared tool is a duty; for each, the best remaining ACTIVE
    specialist whose tool set or purpose overlaps it is named (token
    overlap, registry order breaks ties). Duties with no overlap
    "return to Rowan/Jason". Deterministic: same registry, same draft.
    """
    profile = SP.get_profile(specialist)  # SpecialistNotFound if unknown
    lines = [f"Redelegation draft for {specialist} ({profile.title}).",
             f"Scope: {profile.purpose}",
             "Duties:"]
    for duty in profile.tools:
        best = None
        best_score = 0
        for other in SP.list_specialists():
            if other.name == specialist or other.status != "active":
                continue
            if SP.effective_status(store, owner, other.name) == "retired":
                continue
            score = _tool_overlap(duty, other)
            if score > best_score:
                best, best_score = other, score
        if best is not None:
            lines.append(f"- {duty} -> {best.name} ({best.title}) "
                         f"[overlap {best_score}]")
        else:
            lines.append(f"- {duty} -> returns to Rowan/Jason (no active "
                         "specialist overlaps)")
    return "\n".join(lines)


def decide_case(store: Store, owner: str, case_id: int, decision: str,
                decided_by: str) -> dict:
    """Record the decider's ruling on an open review case.

    decided_by must be a non-empty name and must NOT be 'mentor' —
    Mentor recommends, it never decides. 'train' and 'dismiss' change
    nothing about the specialist's status; 'restrict'/'retire' append
    a specialist_status row. Returns the decided case.
    """
    _ensure_schema(store)
    by = (decided_by or "").strip()
    if not by:
        raise MentorError(
            "decide_case needs a decider name (decided_by)")
    if by.lower() == "mentor":
        raise MentorError(
            "Mentor recommends — it cannot decide cases; a Jason or "
            "Rowan decision is required")
    if decision not in DECISIONS:
        raise MentorError(
            f"decision must be one of {DECISIONS}, got {decision!r}")
    row = store._db.execute(
        "SELECT * FROM review_cases WHERE id = ? AND owner = ?",
        (case_id, owner)).fetchone()
    if row is None:
        raise MentorError(f"review case {case_id} not found")
    case = dict(row)
    if case["status"] != "open":
        raise MentorError(
            f"review case {case_id} is already {case['status']}")
    note = (f"review case {case_id}: {case['recommendation']} "
            f"recommended, {decision} decided by {by}")
    store._db.execute(
        "UPDATE review_cases SET status = 'decided', decided_by = ?, "
        "decision = ?, decided_at = ? WHERE id = ?",
        (by, decision, _now(), case_id))
    if decision == "restrict":
        SP.set_specialist_status(store, owner, case["specialist"],
                                 "restricted", by, note)
    elif decision == "retire":
        SP.set_specialist_status(store, owner, case["specialist"],
                                 "retired", by, note)
    store._db.commit()
    case.update({"status": "decided", "decided_by": by,
                 "decision": decision})
    return case
