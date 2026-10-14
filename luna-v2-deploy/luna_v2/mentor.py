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

Stdlib only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2 import specialists as SP
from luna_v2.store import Store


class MentorError(M.LunaError):
    """Base error for Mentor."""


GRADES = ("strong", "ok", "weak")

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(MENTOR_REVIEWS_SCHEMA)
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
        "specialist": row["specialist"],
        "grade": grade,
        "reason": reason,
        "mission_attributed": mission_attributed,
    }


def grade_runs(store: Store, owner: str, *, limit: int = 20) -> list[dict]:
    """Grade the owner's most recent specialist_runs (newest first).

    Read-only: SELECTs from specialist_runs only, writes nothing.
    """
    SP._ensure_schema(store)
    rows = store._db.execute(
        "SELECT * FROM specialist_runs WHERE owner = ? "
        "ORDER BY id DESC LIMIT ?",
        (owner, limit)).fetchall()
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
