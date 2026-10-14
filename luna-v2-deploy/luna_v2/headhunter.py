"""Headhunter — the hiring agent: prowls for S-tier agent talent.

Jason's directive (2026-10-14): Headhunter thinks of and researches
top-tier agent models and structures, adopts their code only when it is
safe, otherwise studies them and builds our own after looking at theirs.
He stays on the prowl for S-tier agents, but may hire lower-level agents
on probation too — failures get removed.

His powers are bounded by the house rules:
- LICENSE GATE (hard): code is adopted only when the license is in the
  permissive set. Unknown/blank/GPL/proprietary licenses may be studied,
  never adopted. (Jason's safety + downloads doctrine.)
- GATE GATE (hard): no hire without a Warden gate scan reference — a
  gate_scan row id or an honest scan note. No scan, no hire.
- He proposes, Jason or Rowan decides: decide() refuses blank deciders
  and decided_by='headhunter', mirroring Mentor's discipline.
- Probation: new hires serve a review period; past-due probations file
  ONE Guardian suggestion each (deduped while open), closed only by
  Jason or Rowan.
Zero provider calls. Deterministic. Writes only to its own tables plus
guardian_suggestions (best-effort).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlite3 import Row

from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2.store import Store


class HeadhunterError(M.LunaError):
    """Base error for the hiring agent's guard rails."""


class InvalidTransition(HeadhunterError):
    """The candidate's current state does not allow that operation."""


class LicenseGateRefused(HeadhunterError):
    """A 'adopt' recommendation was attempted without a permissive license."""


class HeadhunterDecideRefused(HeadhunterError):
    """decide() was called with a missing or self-serving decider."""


class GateScanMissing(HeadhunterError):
    """mark_hired was called without a Warden gate scan reference."""


# The ONLY licenses under which outside code may be adopted into Luna.
# Everything else may be studied and rebuilt, never adopted verbatim.
PERMISSIVE = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
    "ISC", "Unlicense", "CC0-1.0",
})

KINDS = ("framework", "specialist", "pattern", "code")
TIERS = ("S", "A", "B", "C")
RECOMMENDATIONS = ("adopt", "rebuild", "study", "skip")
STATUSES = ("found", "vetted", "proposed", "approved", "rejected", "hired")
DECISIONS = ("approve", "reject")
PROBATION_OUTCOMES = ("passed", "failed")
PROBATION_STATUSES = ("active", "passed", "failed")

# Lifecycle: a candidate moves forward step by step. 'hired' is entered
# only through mark_hired (which enforces the gate-scan requirement).
TRANSITIONS = {
    "found": ("vetted",),
    "vetted": ("proposed", "rejected"),
    "proposed": ("approved", "rejected"),
    "approved": ("hired",),
    "hired": (),
    "rejected": (),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS candidates (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               name TEXT NOT NULL,
               source_url TEXT DEFAULT '',
               kind TEXT NOT NULL,
               tier TEXT NOT NULL,
               license TEXT DEFAULT '',
               summary TEXT DEFAULT '',
               strengths TEXT DEFAULT '',
               risks TEXT DEFAULT '',
               recommendation TEXT NOT NULL DEFAULT 'study',
               status TEXT NOT NULL DEFAULT 'found',
               decided_by TEXT DEFAULT '',
               decision_note TEXT DEFAULT '',
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               UNIQUE(owner, name))"""
    )
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS probation (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               specialist TEXT NOT NULL,
               candidate_id INTEGER,
               started_at TEXT NOT NULL,
               review_due TEXT NOT NULL,
               status TEXT NOT NULL DEFAULT 'active',
               note TEXT DEFAULT '')"""
    )
    store._db.commit()


def _row(store: Store, candidate_id: int, owner: str) -> Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM candidates WHERE id = ? AND owner = ?",
        (candidate_id, owner)).fetchone()
    if row is None:
        raise HeadhunterError(f"no candidate with id {candidate_id}")
    return row


def _check_adopt_allowed(license: str, recommendation: str) -> None:
    """The license gate: 'adopt' requires a license in PERMISSIVE.

    Refuses at both write paths — add_candidate and any later license /
    recommendation update — so adoption can never be smuggled in via a
    two-step edit.
    """
    if recommendation != "adopt":
        return
    lic = (license or "").strip()
    if lic not in PERMISSIVE:
        raise LicenseGateRefused(
            "license gate: recommendation 'adopt' requires a license in "
            f"{sorted(PERMISSIVE)}; got {lic!r}. Record it as 'study' or "
            "'rebuild' instead — Jason's rule: adopt safe code only.")


# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------

def add_candidate(store: Store, owner: str, name: str, kind: str, tier: str,
                  source_url: str = "", license: str = "",
                  summary: str = "", strengths: str = "", risks: str = "",
                  recommendation: str = "study") -> Row:
    """File a new talent dossier. Idempotent on (owner, name).

    The license gate bites here: recommendation='adopt' is refused unless
    the recorded license is in PERMISSIVE — nothing is written on refusal.
    """
    _ensure_schema(store)
    if kind not in KINDS:
        raise HeadhunterError(f"kind must be one of {KINDS}, got {kind!r}")
    if tier not in TIERS:
        raise HeadhunterError(f"tier must be one of {TIERS}, got {tier!r}")
    if recommendation not in RECOMMENDATIONS:
        raise HeadhunterError(
            f"recommendation must be one of {RECOMMENDATIONS}, "
            f"got {recommendation!r}")
    _check_adopt_allowed(license, recommendation)
    now = _now()
    store._db.execute(
        """INSERT INTO candidates
           (owner, name, source_url, kind, tier, license, summary,
            strengths, risks, recommendation, status,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'found', ?, ?)
           ON CONFLICT(owner, name) DO NOTHING""",
        (owner, name, source_url, kind, tier, license, summary,
         strengths, risks, recommendation, now, now))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM candidates WHERE owner = ? AND name = ?",
        (owner, name)).fetchone()


def list_candidates(store: Store, owner: str, status: str = "") -> list[Row]:
    """Every dossier on file; optionally filtered by status."""
    _ensure_schema(store)
    if status:
        if status not in STATUSES:
            raise HeadhunterError(f"unknown status {status!r}")
        return list(store._db.execute(
            "SELECT * FROM candidates WHERE owner = ? AND status = ? "
            "ORDER BY tier, created_at", (owner, status)))
    return list(store._db.execute(
        "SELECT * FROM candidates WHERE owner = ? ORDER BY tier, created_at",
        (owner,)))


def set_recommendation(store: Store, candidate_id: int, owner: str,
                       recommendation: str) -> Row:
    """Change the recommendation; upgrading TO 'adopt' hits the gate."""
    _ensure_schema(store)
    if recommendation not in RECOMMENDATIONS:
        raise HeadhunterError(
            f"recommendation must be one of {RECOMMENDATIONS}, "
            f"got {recommendation!r}")
    row = _row(store, candidate_id, owner)
    _check_adopt_allowed(row["license"], recommendation)
    store._db.execute(
        "UPDATE candidates SET recommendation = ?, updated_at = ? "
        "WHERE id = ? AND owner = ?",
        (recommendation, _now(), candidate_id, owner))
    store._db.commit()
    return _row(store, candidate_id, owner)


def set_license(store: Store, candidate_id: int, owner: str,
                license: str) -> Row:
    """Record (or correct) the license; a downgrade below PERMISSIVE while
    the recommendation stands at 'adopt' is refused."""
    _ensure_schema(store)
    row = _row(store, candidate_id, owner)
    _check_adopt_allowed(license, row["recommendation"])
    store._db.execute(
        "UPDATE candidates SET license = ?, updated_at = ? "
        "WHERE id = ? AND owner = ?",
        (license, _now(), candidate_id, owner))
    store._db.commit()
    return _row(store, candidate_id, owner)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def advance(store: Store, candidate_id: int, owner: str,
            to_status: str) -> Row:
    """Move a dossier one legal step forward. Illegal jumps raise."""
    _ensure_schema(store)
    if to_status not in STATUSES:
        raise HeadhunterError(f"unknown status {to_status!r}")
    row = _row(store, candidate_id, owner)
    if to_status not in TRANSITIONS[row["status"]]:
        raise InvalidTransition(
            f"candidate {candidate_id} is '{row['status']}': cannot move to "
            f"'{to_status}' (allowed: {TRANSITIONS[row['status']] or 'none'})")
    store._db.execute(
        "UPDATE candidates SET status = ?, updated_at = ? "
        "WHERE id = ? AND owner = ?",
        (to_status, _now(), candidate_id, owner))
    store._db.commit()
    return _row(store, candidate_id, owner)


def decide(store: Store, candidate_id: int, owner: str, decision: str,
           decided_by: str, note: str = "") -> Row:
    """Record the decider's ruling on a proposed candidate.

    Headhunter proposes; Jason or Rowan decides. A blank decider or
    decided_by='headhunter' is refused — mirroring Mentor's discipline.
    """
    _ensure_schema(store)
    by = (decided_by or "").strip()
    if not by:
        raise HeadhunterDecideRefused(
            "decide needs a decider name (decided_by)")
    if by.lower() == "headhunter":
        raise HeadhunterDecideRefused(
            "Headhunter proposes — it cannot decide candidates; a Jason or "
            "Rowan decision is required")
    if decision not in DECISIONS:
        raise HeadhunterDecideRefused(
            f"decision must be one of {DECISIONS}, got {decision!r}")
    to_status = "approved" if decision == "approve" else "rejected"
    row = advance(store, candidate_id, owner, to_status)
    store._db.execute(
        "UPDATE candidates SET decided_by = ?, decision_note = ? "
        "WHERE id = ? AND owner = ?",
        (by, note, candidate_id, owner))
    store._db.commit()
    return _row(store, candidate_id, owner)


def mark_hired(store: Store, candidate_id: int, owner: str,
               gate_scan_ref: str) -> Row:
    """Record the hire. gate_scan_ref — a Warden gate_scans id or an honest
    scan note — is REQUIRED and refused when blank: no gate scan, no hire."""
    _ensure_schema(store)
    ref = (gate_scan_ref or "").strip()
    if not ref:
        raise GateScanMissing(
            "mark_hired needs a Warden gate scan reference (gate_scan_ref): "
            "no scan, no hire")
    row = advance(store, candidate_id, owner, "hired")
    note = (row["decision_note"] or "").rstrip()
    note = (note + "\n" if note else "") + f"gate scan: {ref}"
    store._db.execute(
        "UPDATE candidates SET decision_note = ? WHERE id = ? AND owner = ?",
        (note, candidate_id, owner))
    store._db.commit()
    return _row(store, candidate_id, owner)


# ---------------------------------------------------------------------------
# Probation
# ---------------------------------------------------------------------------

def start_probation(store: Store, owner: str, specialist: str, days: int = 30,
                    candidate_id: int | None = None,
                    note: str = "") -> Row:
    """Open a probation period for a (new or existing) specialist."""
    _ensure_schema(store)
    if days < 1:
        raise HeadhunterError("probation days must be >= 1")
    now = datetime.now(timezone.utc)
    due = (now + timedelta(days=days)).isoformat()
    cur = store._db.execute(
        """INSERT INTO probation
           (owner, specialist, candidate_id, started_at, review_due,
            status, note)
           VALUES (?, ?, ?, ?, ?, 'active', ?)""",
        (owner, specialist, candidate_id, now.isoformat(), due, note))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM probation WHERE id = ?", (cur.lastrowid,)).fetchone()


def list_probation(store: Store, owner: str, status: str = "") -> list[Row]:
    """Probation rows, optionally filtered by status."""
    _ensure_schema(store)
    if status:
        if status not in PROBATION_STATUSES:
            raise HeadhunterError(f"unknown probation status {status!r}")
        return list(store._db.execute(
            "SELECT * FROM probation WHERE owner = ? AND status = ? "
            "ORDER BY review_due", (owner, status)))
    return list(store._db.execute(
        "SELECT * FROM probation WHERE owner = ? ORDER BY review_due",
        (owner,)))


def probation_due(store: Store, owner: str) -> list[Row]:
    """Past-due active probations. Each files ONE Guardian suggestion
    (kind 'probation_review', warning) — deduped while an open one exists,
    following Guardian's dedupe idiom. Best-effort: a Guardian failure
    never breaks the listing.
    """
    _ensure_schema(store)
    now = datetime.now(timezone.utc).isoformat()
    rows = list(store._db.execute(
        "SELECT * FROM probation WHERE owner = ? AND status = 'active' "
        "AND review_due <= ? ORDER BY review_due", (owner, now)))
    for row in rows:
        try:
            G.file_suggestion(
                store, owner,
                check_name="probation_review",
                subject=f"probation: {row['specialist']}",
                severity="warning",
                observation=(
                    f"specialist {row['specialist']!r} is past its probation "
                    f"review date ({row['review_due']}) — pass it, fail it, "
                    "or extend it"),
                evidence=f"probation id {row['id']}, started {row['started_at']}",
                proposed_action=(
                    "Jason or Rowan: headhunter probation close --id "
                    f"{row['id']} --outcome passed|failed --by <you>"))
        except Exception:  # noqa: BLE001 - best-effort filing
            pass
    return rows


def close_probation(store: Store, probation_id: int, owner: str,
                    outcome: str, by: str) -> Row:
    """Close a probation. Only Jason or Rowan may pass or fail a hireling."""
    _ensure_schema(store)
    by_name = (by or "").strip().lower()
    if by_name not in ("jason", "rowan"):
        raise HeadhunterDecideRefused(
            f"close_probation is decided by Jason or Rowan, not {by!r} — "
            "a mentor-level agent cannot end a probation")
    if outcome not in PROBATION_OUTCOMES:
        raise HeadhunterDecideRefused(
            f"outcome must be one of {PROBATION_OUTCOMES}, got {outcome!r}")
    row = store._db.execute(
        "SELECT * FROM probation WHERE id = ? AND owner = ?",
        (probation_id, owner)).fetchone()
    if row is None:
        raise HeadhunterError(f"no probation with id {probation_id}")
    if row["status"] != "active":
        raise HeadhunterError(
            f"probation {probation_id} is already '{row['status']}'")
    store._db.execute(
        "UPDATE probation SET status = ? WHERE id = ? AND owner = ?",
        (outcome, probation_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM probation WHERE id = ?", (probation_id,)).fetchone()
