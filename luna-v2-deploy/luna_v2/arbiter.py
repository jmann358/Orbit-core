"""Arbiter: reality-check counsel — the court's check on its own judgments.

CHARTER (Jason, 2026-10-14): "One new agent — the Arbiter does both
jobs." The jobs are Jason's own framing:

A. YARDSTICK AUDITS — "verify that we're not hiring and firing based
   on a 30 day metric in a department that takes more than 30 days to
   see results." Before a probation verdict or separation lands, the
   Arbiter compares the evaluation window against the role's natural
   RESULT-CYCLE (RESULT_CYCLES_DAYS below; the table also lives in his
   brief) and files FAIR / TOO SHORT / WRONG YARDSTICK. Founding case:
   every active probation in the current cohort serves the identical
   flat 30 days, including roles whose work cannot show its worth
   that fast.
B. REALITY CHECKS — the continuity voice: when a process outcome (a
   gate hold, a probation fail, a metric, a rule) would stop something
   demonstrably working or pass something demonstrably hollow, he
   files a plain-words check — "realistically we're stopping a good
   thing" / "realistically this isn't as good as it sounds" — with the
   records cited, optionally marked OVERRIDE-RECOMMENDED (override it
   now, review or correct after). Jason or Rowan decides; he never
   overrides anything himself.

DISCIPLINE (Canonist/Mentor discipline):
- PROPOSE-ONLY: findings live in arbiter_findings and travel as
  deduped Guardian suggestions. He never edits another record, never
  blocks a process, never closes a probation, never records a
  separation, and decide-by-arbiter is refused in code.
- He never GRADES a specialist's output — that is Mentor's job. He
  audits the yardstick and the moment, not the work.
- Evidence or silence: every finding cites records; a finding with
  blank evidence (or a blank statement) cannot be filed.
- Job A runs as deterministic code over real dates — arithmetic
  doesn't need a voice. Job B is his own thinking: born with a mind
  under Jason's independent-minds ruling, his charter lives in
  luna_v2/minds.py and his consults are broker-accounted dispatches
  recorded verbatim in mind_outputs. A voice doesn't get to fudge
  arithmetic, and arithmetic doesn't get to author his judgment.

Stdlib only.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from luna_v2 import guardian as GD
from luna_v2 import headhunter as HH
from luna_v2 import missions
from luna_v2.store import Store


class ArbiterError(missions.LunaError):
    """Refusals from the Arbiter's discipline."""


KINDS = ("yardstick", "reality")
YARDSTICK_VERDICTS = ("fair", "too_short", "wrong_yardstick")
REALITY_VERDICTS = ("stopping_a_good_thing", "not_as_good_as_it_sounds",
                    "holds_up")
VERDICTS = YARDSTICK_VERDICTS + REALITY_VERDICTS
STATUSES = ("open", "decided", "dismissed")
DECIDE_ACTIONS = ("accept", "dismiss")
GUARDIAN_CHECK = "arbiter_finding"

_VERDICT_FOR_KIND = {"yardstick": YARDSTICK_VERDICTS,
                     "reality": REALITY_VERDICTS}

# ---------------------------------------------------------------------------
# The result-cycle table (v1, conservative — the brief carries the why)
# ---------------------------------------------------------------------------
# Days until a role's FIRST real results can honestly be judged. Roles
# not listed are assumed to fit the house default below and are never
# flagged: the table names only the cycles the evidence supports.
DEFAULT_CYCLE_DAYS = 30
RESULT_CYCLES_DAYS = {
    "cartographer": 90,   # research campaigns: multi-week evidence arcs
    "steward": 90,        # projects across months (Christmas horizon)
    "lantern": 90,        # campaign stages are multi-week arcs
    "arbiter": 90,        # judges verdicts; verdicts happen at review dates
    "canonist": 60,       # canon drift accrues slowly, over months
    "trainer": 60,        # plans pay off over weeks of graded runs
    "tallyman": 60,       # efficiency needs several usage/sync cycles
    "weaver": 60,         # patterns emerge over accumulated missions
    "marshal": 60,        # coordination quality shows over many missions
}


def result_cycle_days(specialist: str) -> int:
    """The conservative first-results cycle for one role, in days."""
    return RESULT_CYCLES_DAYS.get((specialist or "").strip().lower(),
                                  DEFAULT_CYCLE_DAYS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS arbiter_findings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('yardstick','reality')),
    subject       TEXT NOT NULL,
    verdict       TEXT NOT NULL,
    statement     TEXT NOT NULL,   -- the check, in plain words
    evidence      TEXT NOT NULL,   -- the records cited — never vibes
    override_recommended INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','decided','dismissed')),
    decided_by    TEXT NOT NULL DEFAULT '',
    annotation    TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_arbiter_findings_owner
    ON arbiter_findings(owner, status);
"""
_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_arbiter_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._arbiter_schema_v = _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Filing (dedupe: an open finding for the same kind+subject is not refiled)
# ---------------------------------------------------------------------------
def _validate(kind: str, verdict: str, subject: str, statement: str,
              evidence: str) -> None:
    if kind not in KINDS:
        raise ArbiterError(f"kind must be one of {KINDS}")
    if verdict not in _VERDICT_FOR_KIND[kind]:
        raise ArbiterError(
            f"a {kind} finding's verdict must be one of "
            f"{_VERDICT_FOR_KIND[kind]}; got {verdict!r}")
    if not (subject or "").strip():
        raise ArbiterError("a finding needs a subject")
    if not (statement or "").strip():
        raise ArbiterError(
            "a finding needs its statement — the check, in plain words")
    if not (evidence or "").strip():
        raise ArbiterError(
            "evidence or silence: a finding must cite the records it "
            "rests on")


def _file_finding(store: Store, owner: str, kind: str, subject: str,
                  verdict: str, statement: str, evidence: str,
                  override_recommended: bool = False) -> tuple:
    """File one finding; return (row, created)."""
    _validate(kind, verdict, subject, statement, evidence)
    _ensure_schema(store)
    existing = store._db.execute(
        "SELECT * FROM arbiter_findings WHERE owner = ? AND kind = ? "
        "AND subject = ? AND status = 'open'",
        (owner, kind, subject)).fetchone()
    if existing is not None:
        return existing, False
    cur = store._db.execute(
        "INSERT INTO arbiter_findings (owner, kind, subject, verdict, "
        "statement, evidence, override_recommended, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (owner, kind, subject, verdict, statement, evidence,
         1 if override_recommended else 0, _now()))
    store._db.commit()
    row = store._db.execute(
        "SELECT * FROM arbiter_findings WHERE id = ?",
        (cur.lastrowid,)).fetchone()
    return row, True


def _file_guardian(store: Store, owner: str, finding: sqlite3.Row) -> bool:
    """Carry a finding to Rowan as one deduped Guardian suggestion."""
    subject = f"arbiter:{finding['kind']}:{finding['subject']}"
    observation = (f"Arbiter finding [{finding['kind']}/"
                   f"{finding['verdict']}]: {finding['subject']} — "
                   f"{finding['statement']}")
    action = (f"Jason/Rowan decides (arbiter finding {finding['id']}; "
              f"the Arbiter flags, humans rule — he never decides a "
              f"verdict, grades output, or edits a record)")
    if finding["override_recommended"]:
        action = ("OVERRIDE RECOMMENDED — Jason/Rowan: consider "
                  "overriding the outcome now and reviewing after. "
                  + action)
    _, created = GD._file_one(
        store, owner, GUARDIAN_CHECK, subject, "warning",
        observation, finding["evidence"], action)
    return created


def list_findings(store: Store, owner: str, status: str = "") -> list:
    """Arbiter findings, optionally filtered by status."""
    _ensure_schema(store)
    if status and status not in STATUSES:
        raise ArbiterError(f"status must be one of {STATUSES}")
    q = ("SELECT * FROM arbiter_findings WHERE owner = ? "
         + ("AND status = ? " if status else "")
         + "ORDER BY id")
    return store._db.execute(q, (owner, status) if status else (owner,)).fetchall()


def decide_finding(store: Store, owner: str, finding_id: int,
                   decided_by: str, action: str,
                   annotation: str = "") -> sqlite3.Row:
    """Record Jason/Rowan's decision on a finding. Propose-only
    discipline: a blank decider or decided_by='arbiter' is refused."""
    _ensure_schema(store)
    by = (decided_by or "").strip()
    if not by:
        raise ArbiterError("decide needs a decider name (decided_by)")
    if by.lower() == "arbiter":
        raise ArbiterError(
            "the Arbiter proposes — it cannot decide findings; "
            "a Jason or Rowan decision is required")
    if action not in DECIDE_ACTIONS:
        raise ArbiterError(f"action must be one of {DECIDE_ACTIONS}")
    row = store._db.execute(
        "SELECT * FROM arbiter_findings WHERE id = ? AND owner = ?",
        (finding_id, owner)).fetchone()
    if row is None:
        raise ArbiterError(f"no arbiter finding {finding_id}")
    if row["status"] != "open":
        raise ArbiterError(
            f"finding {finding_id} is already {row['status']}; "
            f"decided findings stand, new audits file new ones")
    status = "decided" if action == "accept" else "dismissed"
    store._db.execute(
        "UPDATE arbiter_findings SET status = ?, decided_by = ?, "
        "annotation = ?, decided_at = ? WHERE id = ? AND owner = ?",
        (status, by, annotation.strip(), _now(), finding_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM arbiter_findings WHERE id = ?",
        (finding_id,)).fetchone()


# ---------------------------------------------------------------------------
# Job B — reality checks (filed by Jason/Rowan, incl. from his consults)
# ---------------------------------------------------------------------------
def file_reality_check(store: Store, owner: str, subject: str,
                       verdict: str, statement: str, evidence: str,
                       override_recommended: bool = False,
                       filed_by: str = "") -> sqlite3.Row:
    """Record one reality check. This is the human-side door for Job B:
    Jason or Rowan files the check (including verbatim from the
    Arbiter's own consult words — his thinking enters the book through
    this door, never by his own hand). One deduped Guardian suggestion
    travels with each new check."""
    _validate("reality", verdict, subject, statement, evidence)
    row, created = _file_finding(store, owner, "reality", subject,
                                 verdict, statement, evidence,
                                 override_recommended)
    if created:
        _file_guardian(store, owner, row)
    return row


# ---------------------------------------------------------------------------
# Job A — the yardstick audit (deterministic arithmetic over real dates)
# ---------------------------------------------------------------------------
def audit_windows(store: Store, owner: str, *,
                  today: datetime | None = None) -> dict:
    """Audit every ACTIVE probation window against its role's cycle.

    For each probation: window = review_due - started_at, in days;
    cycle = result_cycle_days(specialist). window < cycle files a
    TOO SHORT yardstick finding (+ one deduped Guardian suggestion);
    otherwise the verdict is FAIR and is reported, not filed — the
    book records what needs a human, the return value reports all of
    it. A re-audit of unchanged windows files nothing new.
    Zero provider calls, zero spend.
    """
    _ensure_schema(store)
    now = today or datetime.now(timezone.utc)
    verdicts = []
    new_findings = []
    new_suggestions = 0
    for p in HH.list_probation(store, owner, status="active"):
        name = p["specialist"]
        started = _parse(p["started_at"])
        due = _parse(p["review_due"])
        window_days = (due - started).days
        cycle = result_cycle_days(name)
        elapsed = max(0, (now - started).days)
        remaining = (due - now).days
        entry = {"specialist": name, "probation_id": p["id"],
                 "window_days": window_days, "cycle_days": cycle,
                 "elapsed_days": elapsed, "remaining_days": remaining,
                 "verdict": "fair"}
        if window_days < cycle:
            entry["verdict"] = "too_short"
            statement = (
                f"Realistically, {name}'s probation window is too "
                f"short to judge: the role needs about {cycle} days "
                f"to show first real results and the window allows "
                f"{window_days}. A verdict at the review date would "
                f"judge the scaffolding, not the work.")
            evidence = (
                f"probation {p['id']} ({name}): started "
                f"{p['started_at'][:10]}, review due "
                f"{p['review_due'][:10]} — window {window_days} day(s), "
                f"{elapsed} elapsed, {remaining} remaining; Arbiter "
                f"result-cycle table: {cycle} day(s) for {name} "
                f"(Luna-Arbiter-Brief-2026-10-14).")
            row, created = _file_finding(
                store, owner, "yardstick", f"probation:{name}",
                "too_short", statement, evidence)
            if created:
                new_findings.append(row)
                new_suggestions += _file_guardian(store, owner, row)
        verdicts.append(entry)
    return {
        "owner": owner,
        "checked": len(verdicts),
        "verdicts": verdicts,
        "too_short": sum(1 for v in verdicts
                         if v["verdict"] == "too_short"),
        "new_findings": len(new_findings),
        "guardian_suggestions_filed": new_suggestions,
        "finding_ids": [r["id"] for r in new_findings],
    }
