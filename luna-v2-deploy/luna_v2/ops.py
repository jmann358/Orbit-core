"""Ops — Luna's pulse feed and the problem→solution pipeline.

Bundle B of Jason's workload directive (2026-10-14 ~19:48 EDT):
Luna emits constant updates, and specialists report what doesn't
work AND suggest the solution — with solutions proven and
pre-approved by Rowan before they ever reach Jason as answers.

Two record families, both additive, both owned here:

- pulse_events — the constant-updates feed. Every meaningful
  transition lands here as one short line (started / blocked /
  failed / fix_proposed / fix_approved / done), rendered in the
  Inbox as "Luna updates" and printable via `ops feed`.

- problem_reports — the problem→solution pipeline, with two laws
  enforced in code, not by convention:

  THE REPORT LAW: a problem report is REFUSED without evidence
  and REFUSED without a proposed solution. A bare "it's broken"
  is not a report; nobody files one.

  THE APPROVAL LAW: a proposed solution becomes rowan_approved
  ONLY with a verification note — what proved it (tested on a
  copy, a prior receipt, a cited record). No note, no approval;
  an unapproved solution is stamped UNPROVEN wherever it is
  shown. The reporting specialist can never approve its own
  fix. Consequential fixes take the distinct jason_needed state
  instead of Rowan's stamp. A fix is marked applied only with
  its result recorded, which closes the report.

Workload transitions and Conductor ticks emit pulses through
emit_pulse(); Guardian's scan files problem reports through
file_report(). This module never approves anything itself —
decisions arrive from named deciders via the CLI.

Stdlib only.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from luna_v2 import missions
from luna_v2 import specialists as SP
from luna_v2.store import Store


class OpsError(missions.LunaError):
    """Refusals from the report law / approval law."""


PULSE_KINDS = ("started", "blocked", "failed",
               "fix_proposed", "fix_approved", "done")
SOLUTION_STATES = ("proposed", "rowan_approved", "jason_needed",
                   "rejected", "applied")
REPORT_STATUSES = ("open", "closed")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pulse_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    ts         TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('started','blocked',
               'failed','fix_proposed','fix_approved','done')),
    specialist TEXT NOT NULL,
    summary    TEXT NOT NULL,
    ref        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pulse_events_owner
    ON pulse_events(owner, id);
CREATE TABLE IF NOT EXISTS problem_reports (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    owner            TEXT NOT NULL,
    ts               TEXT NOT NULL,
    specialist       TEXT NOT NULL,
    problem          TEXT NOT NULL,
    evidence         TEXT NOT NULL,
    proposed_solution TEXT NOT NULL,
    solution_status  TEXT NOT NULL DEFAULT 'proposed'
                     CHECK (solution_status IN ('proposed',
                     'rowan_approved','jason_needed','rejected',
                     'applied')),
    verification_note TEXT NOT NULL DEFAULT '',
    decided_by       TEXT NOT NULL DEFAULT '',
    applied_result   TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','closed')),
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_problem_reports_owner
    ON problem_reports(owner, status, solution_status);
"""
_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_ops_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._ops_schema_v = _SCHEMA_VERSION


def _check_specialist(specialist: str) -> str:
    name = (specialist or "").strip().lower()
    if name not in SP.SPECIALISTS:
        raise OpsError(
            f"unknown specialist {specialist!r} — only registered "
            f"specialists file ops records")
    return name


# ---------------------------------------------------------------------------
# Pulse feed
# ---------------------------------------------------------------------------
def emit_pulse(store: Store, owner: str, kind: str, specialist: str,
               summary: str, ref: str = "") -> sqlite3.Row:
    """Record one pulse event. The feed is the proof of motion:
    short, factual, attributed."""
    _ensure_schema(store)
    if kind not in PULSE_KINDS:
        raise OpsError(f"pulse kind must be one of {PULSE_KINDS}")
    name = _check_specialist(specialist)
    if not (summary or "").strip():
        raise OpsError("a pulse event needs a summary")
    cur = store._db.execute(
        "INSERT INTO pulse_events (owner, ts, kind, specialist, "
        "summary, ref) VALUES (?, ?, ?, ?, ?, ?)",
        (owner, _now(), kind, name, summary.strip(),
         (ref or "").strip()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM pulse_events WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_pulses(store: Store, owner: str, *, limit: int = 20,
                kind: str = "") -> list:
    """Newest pulse events first."""
    _ensure_schema(store)
    q = "SELECT * FROM pulse_events WHERE owner = ?"
    args: list = [owner]
    if kind:
        if kind not in PULSE_KINDS:
            raise OpsError(f"pulse kind must be one of {PULSE_KINDS}")
        q += " AND kind = ?"
        args.append(kind)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(int(limit))
    return store._db.execute(q, args).fetchall()


# ---------------------------------------------------------------------------
# Problem reports — the report law and the approval law
# ---------------------------------------------------------------------------
def file_report(store: Store, owner: str, specialist: str,
                problem: str, evidence: str,
                proposed_solution: str) -> sqlite3.Row:
    """File one problem report.

    THE REPORT LAW: evidence is REQUIRED and a proposed solution
    is REQUIRED — a report carrying either blank is refused and
    writes nothing. Deduped: an OPEN report from the same
    specialist with the same problem text is returned, not
    refiled. Filing emits a fix_proposed pulse.
    """
    _ensure_schema(store)
    name = _check_specialist(specialist)
    if not (problem or "").strip():
        raise OpsError("a problem report needs the problem, in words")
    if not (evidence or "").strip():
        raise OpsError(
            "the report law: evidence is required — what shows "
            "this is broken, not just that it feels broken")
    if not (proposed_solution or "").strip():
        raise OpsError(
            "the report law: a proposed solution is required — "
            "never report a problem without the fix you propose")
    existing = store._db.execute(
        "SELECT * FROM problem_reports WHERE owner = ? AND "
        "specialist = ? AND problem = ? AND status = 'open'",
        (owner, name, problem.strip())).fetchone()
    if existing is not None:
        return existing
    now = _now()
    cur = store._db.execute(
        "INSERT INTO problem_reports (owner, ts, specialist, "
        "problem, evidence, proposed_solution, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner, now, name, problem.strip(), evidence.strip(),
         proposed_solution.strip(), now))
    store._db.commit()
    row = _get_report(store, owner, cur.lastrowid)
    emit_pulse(store, owner, "fix_proposed", name,
               f"problem report {row['id']}: {row['problem'][:80]} "
               f"— fix proposed: {row['proposed_solution'][:80]}",
               ref=f"problem-report:{row['id']}")
    return row


def _get_report(store: Store, owner: str,
                report_id: int) -> sqlite3.Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM problem_reports WHERE id = ? AND owner = ?",
        (report_id, owner)).fetchone()
    if row is None:
        raise OpsError(f"no problem report {report_id}")
    return row


def get_report(store: Store, owner: str, report_id: int) -> sqlite3.Row:
    return _get_report(store, owner, report_id)


def list_reports(store: Store, owner: str, *, status: str = "",
                 solution_status: str = "") -> list:
    """Problem reports, newest first, optionally filtered."""
    _ensure_schema(store)
    q = "SELECT * FROM problem_reports WHERE owner = ?"
    args: list = [owner]
    if status:
        if status not in REPORT_STATUSES:
            raise OpsError(
                f"report status must be one of {REPORT_STATUSES}")
        q += " AND status = ?"
        args.append(status)
    if solution_status:
        if solution_status not in SOLUTION_STATES:
            raise OpsError(
                f"solution status must be one of {SOLUTION_STATES}")
        q += " AND solution_status = ?"
        args.append(solution_status)
    q += " ORDER BY id DESC"
    return store._db.execute(q, args).fetchall()


def _set_report(store: Store, owner: str, report_id: int,
                **fields) -> sqlite3.Row:
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    store._db.execute(
        f"UPDATE problem_reports SET {cols} WHERE id = ? AND owner = ?",
        (*fields.values(), report_id, owner))
    store._db.commit()
    return _get_report(store, owner, report_id)


def _open_proposed(store: Store, owner: str,
                   report_id: int) -> sqlite3.Row:
    row = _get_report(store, owner, report_id)
    if row["status"] != "open":
        raise OpsError(f"problem report {report_id} is closed")
    if row["solution_status"] != "proposed":
        raise OpsError(
            f"problem report {report_id}'s solution is already "
            f"{row['solution_status']} — decisions are not rewritten")
    return row


def approve_solution(store: Store, owner: str, report_id: int, *,
                     approved_by: str,
                     verification_note: str) -> sqlite3.Row:
    """proposed → rowan_approved.

    THE APPROVAL LAW: the verification note is REQUIRED (what
    proved the fix: tested on a copy, a prior receipt, a cited
    record) — no note, no approval. The reporting specialist can
    never approve its own fix.
    """
    if not (verification_note or "").strip():
        raise OpsError(
            "the approval law: approving requires a verification "
            "note — what proved this fix (tested on a copy, a "
            "prior receipt, a cited record). Without proof the "
            "solution stays UNPROVEN")
    by = (approved_by or "").strip().lower()
    if not by:
        raise OpsError("approving requires a named approver")
    row = _open_proposed(store, owner, report_id)
    if by == row["specialist"]:
        raise OpsError(
            "the approval law: a specialist never approves its "
            "own fix — the proof gets checked by someone else")
    out = _set_report(store, owner, report_id,
                      solution_status="rowan_approved",
                      verification_note=verification_note.strip(),
                      decided_by=by)
    emit_pulse(store, owner, "fix_approved", row["specialist"],
               f"fix approved for problem report {report_id} by "
               f"{by}: {row['proposed_solution'][:80]}",
               ref=f"problem-report:{report_id}")
    return out


def mark_jason_needed(store: Store, owner: str, report_id: int, *,
                      decided_by: str = "rowan") -> sqlite3.Row:
    """proposed → jason_needed: the consequential-fix state. This
    is a routing decision, not an approval — Jason decides."""
    by = (decided_by or "").strip().lower()
    if not by:
        raise OpsError("marking jason_needed requires a named decider")
    _open_proposed(store, owner, report_id)
    return _set_report(store, owner, report_id,
                       solution_status="jason_needed", decided_by=by)


def reject_solution(store: Store, owner: str, report_id: int, *,
                    decided_by: str) -> sqlite3.Row:
    """proposed → rejected. The report closes: the problem record
    stays on the books, the proposed fix does not proceed."""
    by = (decided_by or "").strip().lower()
    if not by:
        raise OpsError("rejecting requires a named decider")
    _open_proposed(store, owner, report_id)
    return _set_report(store, owner, report_id,
                       solution_status="rejected", decided_by=by,
                       status="closed")


def mark_applied(store: Store, owner: str, report_id: int, *,
                 applied_result: str,
                 decided_by: str = "") -> sqlite3.Row:
    """rowan_approved|jason_needed → applied, report closed.

    The result is REQUIRED — 'applied' without what happened is
    not a record. Applying an unapproved or rejected solution is
    refused: approval comes first, always.
    """
    if not (applied_result or "").strip():
        raise OpsError(
            "marking applied requires the result — what was done "
            "and what it changed, in words")
    row = _get_report(store, owner, report_id)
    if row["status"] != "open":
        raise OpsError(f"problem report {report_id} is closed")
    if row["solution_status"] not in ("rowan_approved", "jason_needed"):
        raise OpsError(
            f"problem report {report_id}'s solution is "
            f"{row['solution_status']} — only an approved fix "
            f"(rowan_approved, or jason_needed decided by Jason) "
            f"can be marked applied")
    out = _set_report(store, owner, report_id,
                      solution_status="applied",
                      applied_result=applied_result.strip(),
                      status="closed")
    emit_pulse(store, owner, "done", row["specialist"],
               f"fix applied for problem report {report_id}: "
               f"{applied_result.strip()[:100]}",
               ref=f"problem-report:{report_id}")
    return out


# ---------------------------------------------------------------------------
# The digest — Jason's format
# ---------------------------------------------------------------------------
def digest(store: Store, owner: str, *, limit: int = 10) -> str:
    """DONE (with proof refs) · BROKEN + the fix (approval state;
    UNPROVEN stamped on anything not rowan_approved) · NEEDS YOU
    (jason_needed reports and blocked work items — only what is
    truly his). Deterministic text from the real records."""
    _ensure_schema(store)
    lines = [f"LUNA OPS DIGEST — {owner}"]
    # DONE: applied fixes (with their recorded results) + done pulses
    lines.append("DONE")
    applied = list_reports(store, owner, solution_status="applied")
    done_pulses = list_pulses(store, owner, limit=limit, kind="done")
    if not applied and not done_pulses:
        lines.append("- nothing completed yet")
    for r in applied[:limit]:
        lines.append(
            f"- fix applied (problem report {r['id']}, "
            f"{r['specialist']}): {r['problem']} — result: "
            f"{r['applied_result']}")
    for p in done_pulses:
        if p["ref"].startswith("problem-report:"):
            continue  # applied fixes already listed with results
        ref = f" [{p['ref']}]" if p["ref"] else ""
        lines.append(
            f"- {p['specialist']}: {p['summary']} ({p['ts']}){ref}")
    # BROKEN: every open report, with its fix and approval state
    lines.append("BROKEN")
    open_reports = [r for r in list_reports(store, owner, status="open")]
    if not open_reports:
        lines.append("- nothing broken on the books")
    for r in open_reports:
        state = r["solution_status"]
        stamp = "" if state == "rowan_approved" else " [UNPROVEN]"
        proof = (f" — proof: {r['verification_note']}"
                 if r["verification_note"] else "")
        lines.append(
            f"- problem report {r['id']} [{r['specialist']}] "
            f"{r['problem']}")
        lines.append(f"  evidence: {r['evidence']}")
        lines.append(
            f"  fix: {r['proposed_solution']} (state: {state})"
            f"{stamp}{proof}")
    # NEEDS YOU: jason_needed reports + blocked work items only
    lines.append("NEEDS YOU")
    needs = []
    for r in open_reports:
        if r["solution_status"] == "jason_needed":
            needs.append(
                f"- problem report {r['id']} [{r['specialist']}] "
                f"awaits your call: {r['problem']} — proposed fix: "
                f"{r['proposed_solution']}")
    blocked = []
    if store._db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'work_queue'").fetchone():
        blocked = store._db.execute(
            "SELECT * FROM work_queue WHERE owner = ? AND "
            "status = 'blocked' ORDER BY id", (owner,)).fetchall()
    for w in blocked:
        needs.append(
            f"- work item {w['id']} [{w['specialist']}] blocked: "
            f"{w['title']} — blocker: {w['blocker']}")
    lines.extend(needs if needs else ["- nothing needs you"])
    return "\n".join(lines)
