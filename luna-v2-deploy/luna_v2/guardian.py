"""Guardian: Luna's liaison to Rowan, now active.

Jason's direction (2026-10-13): Luna gets a team of specialists; Guardian
is the ninth, facing UP to Rowan. While Luna is young, everything she
cannot handle herself routes up through Guardian as structured
suggestions Rowan can see and act on.

Design rules (deliberate):
- READ-ONLY over Luna's state. Guardian SELECTs from missions, steps,
  approvals, the broker tables, and specialist_runs. Its only writes
  are its own suggestion records (guardian_suggestions). It never
  modifies missions, the broker, usage, or anything else, and it makes
  ZERO provider calls — a scan never spends free fuel.
- State, not feelings. Luna's chat persona has no visibility into her
  own system state (verified 2026-10-13); Guardian reads the real
  records instead: the DB, the broker ledger, the run logs.
- Structured suggestions: check name, subject, severity, observation,
  evidence, proposed action. Rowan acts; Guardian tracks each
  suggestion until it is acknowledged, done, or declined.
- Dedupe: a check+subject with an OPEN suggestion is not refiled on
  rescan. Once a suggestion is resolved, a still-true condition may
  file a fresh one (each escalation is a new, deliberate record).

Stdlib only.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from luna_v2 import broker as B
from luna_v2 import missions as M
from luna_v2 import specialists as SP
from luna_v2.store import Store


class GuardianError(M.LunaError):
    """Base error for Guardian."""


class SuggestionNotFound(GuardianError):
    """No suggestion with that id."""


class BadResolution(GuardianError):
    """A resolution status outside the allowed set."""


SEVERITIES = ("info", "warning", "critical")
# Inbox shows the most severe first; within a severity, the oldest
# first — a stale open suggestion should surface before a fresh one.
_RESOLUTIONS = ("acknowledged", "done", "declined")

SCHEMA = """
CREATE TABLE IF NOT EXISTS guardian_suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    check_name      TEXT NOT NULL,
    subject         TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
    observation     TEXT NOT NULL DEFAULT '',
    evidence        TEXT NOT NULL DEFAULT '',
    proposed_action TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','acknowledged','done','declined')),
    resolution_note TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    resolved_at     TEXT,
    dedupe_key      TEXT NOT NULL
);

-- One open suggestion per check+subject. A resolved suggestion no
-- longer holds the key, so a still-true condition may refile after
-- resolution — each refile is a deliberate new record.
CREATE UNIQUE INDEX IF NOT EXISTS guardian_suggestions_open_dedupe
    ON guardian_suggestions(dedupe_key) WHERE status = 'open';
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.executescript(SCHEMA)
    store._db.commit()


# ---------------------------------------------------------------------------
# The checks (each returns findings; none writes, none calls a provider)
# ---------------------------------------------------------------------------
def _check_stuck_missions(store: Store, owner: str) -> list[dict]:
    """info: a mission still open whose steps are not all done/skipped.

    Design decision: an open mission with NO steps at all is not
    flagged — with no steps there is nothing 'stuck'; Rowan decides
    whether an empty open mission deserves a suggestion.
    """
    out = []
    for m in store.list_missions(owner):
        if m["status"] != "open":
            continue
        steps = store.list_steps(m["id"])
        open_steps = [s for s in steps
                      if s["status"] not in ("done", "skipped")]
        if steps and open_steps:
            out.append({
                "check_name": "stuck_mission",
                "subject": f"mission {m['id']}",
                "severity": "info",
                "observation": (
                    f"mission {m['id']} {m['title']!r} is open with "
                    f"{len(open_steps)} of {len(steps)} steps not "
                    "done/skipped"),
                "evidence": (
                    "open steps: " + ", ".join(
                        f"{s['id']} ({s['description'][:60]})"
                        for s in open_steps)),
                "proposed_action": (
                    "Rowan: investigate — if the mission is abandoned, "
                    "close it (skip the dead steps); if it is real work, "
                    "drive it to a receipt or hand it to a specialist."),
            })
    return out


def _check_awaiting_approval(store: Store, owner: str) -> list[dict]:
    """info: an open consequential step with NO approval record on file.

    Design decision: only steps with zero approvals are flagged. The
    missions module is latest-decision-wins, so a rejected step that
    has not been re-approved is a judgment call for Rowan, not an
    unambiguous 'waiting on Jason' — Guardian flags the clear case.
    """
    out = []
    for m in store.list_missions(owner):
        if m["status"] != "open":
            continue
        for s in store.list_steps(m["id"]):
            if s["kind"] != "consequential" or s["status"] != "open":
                continue
            if store.list_approvals(s["id"]):
                continue
            out.append({
                "check_name": "awaiting_approval",
                "subject": f"step {s['id']}",
                "severity": "info",
                "observation": (
                    f"step {s['id']} {s['description'][:70]!r} of mission "
                    f"{m['id']} is consequential, open, and has no "
                    "approval decision — it is waiting on Jason"),
                "evidence": (
                    f"mission {m['id']} {m['title']!r}; step kind="
                    f"{s['kind']}, status={s['status']}; "
                    f"{len(store.list_approvals(s['id']))} approvals on file"),
                "proposed_action": (
                    "Rowan: if this step genuinely needs a decision, "
                    "surface it to Jason with the evidence attached; "
                    "otherwise skip it."),
            })
    return out


def _check_failed_runs(store: Store, owner: str) -> list[dict]:
    """warning: specialist_runs rows in failed state.

    The table is owned by the specialists module; ensuring its schema
    is idempotent DDL, not data. Guardian never touches the rows.
    """
    SP._ensure_schema(store)
    out = []
    for r in store._db.execute(
            "SELECT * FROM specialist_runs WHERE owner = ? AND status = 'failed' "
            "ORDER BY id", (owner,)).fetchall():
        out.append({
            "check_name": "failed_run",
            "subject": f"specialist-run {r['id']}",
            "severity": "warning",
            "observation": (
                f"{r['specialist']} run {r['id']} failed "
                f"(mission {r['mission_id']}, step {r['step_id']})"),
            "evidence": f"run error: {r['error'] or '(no error recorded)'}",
            "proposed_action": (
                "Rowan: investigate the run record; if the failure was "
                "transient, re-run the task, else carry the work a "
                "different way and mark this done."),
        })
    return out


def _check_allocation_burn(store: Store, owner: str) -> list[dict]:
    """warning at >=80%, critical at >=95% of a production allocation used.

    Uses the broker's own period math (list_allocations), so 'used' is
    the exact current-period consumption.

    Design decisions:
    - Only routable allocations are watched (active, production-allowed,
      known quota). Warning about a retired provider, an
      evaluation-only key, or an unknown quota would be noise — Guardian
      cannot compute a percentage against 'unknown'.
    - record_usage already refuses usage past the allowance, so a burn
      over 100% can only exist from older data; percentages are still
      reported as-is.
    """
    out = []
    for a in B.list_allocations(store, owner):
        if a.allowance is None or not a.routable:
            continue
        pct = (a.used / a.allowance * 100.0) if a.allowance else 0.0
        severity = ("critical" if pct >= 95.0
                    else "warning" if pct >= 80.0 else None)
        if severity is None:
            continue
        out.append({
            "check_name": "allocation_burn",
            "subject": f"{a.provider}/{a.unit}",
            "severity": severity,
            "observation": (
                f"{a.provider}/{a.unit}: {pct:.1f}% of the "
                f"{a.period} free allocation used"),
            "evidence": (
                f"used {a.used:g} of {a.allowance:g} {a.unit} this "
                f"{a.period} period; resets in {B._fmt_timedelta(a.resets_in)}"),
            "proposed_action": (
                "Rowan: route future work to another provider; if none "
                "is suitable, wait for the reset — or ask Jason about "
                "adding a second free tier (OpenRouter / Cloudflare)."),
        })
    return out


def _check_step_states(store: Store, owner: str) -> list[dict]:
    """warning: any step in an unexpected status.

    Design decision: the steps table's CHECK constraint only allows
    open/done/skipped, so this check fires nothing today. It exists as
    a safety net: if a later schema change introduces a 'failed' (or
    any other) step state, Guardian notices it without a code change.
    """
    known = {"open", "done", "skipped"}
    out = []
    for m in store.list_missions(owner):
        for s in store.list_steps(m["id"]):
            if s["status"] not in known:
                out.append({
                    "check_name": "failed_step",
                    "subject": f"step {s['id']}",
                    "severity": "warning",
                    "observation": (
                        f"step {s['id']} of mission {m['id']} is in an "
                        f"unexpected status {s['status']!r}"),
                    "evidence": (
                        f"mission {m['id']} {m['title']!r}; "
                        f"result={s['result'][:80]!r}"),
                    "proposed_action": (
                        "Rowan: inspect the step and its mission; decide "
                        "whether it can finish, must be redone, or should "
                        "be skipped."),
                })
    return out


_CHECKS = (
    _check_stuck_missions,
    _check_awaiting_approval,
    _check_failed_runs,
    _check_allocation_burn,
    _check_step_states,
)


# ---------------------------------------------------------------------------
# Filing, inbox, resolution
# ---------------------------------------------------------------------------
def _file_one(store: Store, owner: str, check_name: str, subject: str,
              severity: str, observation: str, evidence: str,
              proposed_action: str) -> tuple:
    """File one suggestion. Returns (row, created): created is False when
    an OPEN suggestion with the same dedupe_key already existed."""
    if severity not in SEVERITIES:
        raise GuardianError(f"severity must be one of {SEVERITIES}")
    _ensure_schema(store)
    key = f"{check_name}:{subject}"
    existing = store._db.execute(
        "SELECT * FROM guardian_suggestions "
        "WHERE dedupe_key = ? AND status = 'open'", (key,)).fetchone()
    if existing is not None:
        return existing, False
    try:
        cur = store._db.execute(
            "INSERT INTO guardian_suggestions (owner, check_name, subject, "
            "severity, observation, evidence, proposed_action, status, "
            "created_at, dedupe_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
            (owner, check_name, subject, severity, observation, evidence,
             proposed_action, _now(), key))
        store._db.commit()
    except sqlite3.IntegrityError:
        # A concurrent scan filed it first; return the existing row.
        store._db.rollback()
        existing = store._db.execute(
            "SELECT * FROM guardian_suggestions "
            "WHERE dedupe_key = ? AND status = 'open'", (key,)).fetchone()
        return existing, False
    row = store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE id = ?",
        (cur.lastrowid,)).fetchone()
    return row, True


def file_suggestion(store: Store, owner: str, check_name: str, subject: str,
                    severity: str, observation: str, evidence: str,
                    proposed_action: str) -> sqlite3.Row | None:
    """File one suggestion. If an OPEN suggestion with the same dedupe_key
    already exists, return it instead of refiling. Resolved suggestions
    do not block refiling."""
    row, _ = _file_one(store, owner, check_name, subject, severity,
                       observation, evidence, proposed_action)
    return row


def _ops_hook(store: Store, owner: str, suggestion) -> None:
    """Bundle B: a warning/critical suggestion also files a
    problem report in the ops pipeline — the suggestion's proposed
    action becomes the proposed solution and its evidence is
    copied verbatim, so the problem arrives WITH its fix, per the
    report law. Deduped twice over: scan only calls this for
    newly filed suggestions, and the ops filer dedupes open
    reports on specialist+problem. Info suggestions stay plain
    suggestions; only warning/critical rise to problem reports."""
    if suggestion["severity"] not in ("warning", "critical"):
        return
    from luna_v2 import ops as OPS
    OPS.file_report(
        store, owner, "guardian",
        problem=(f"guardian {suggestion['check_name']} on "
                 f"{suggestion['subject']}: "
                 f"{suggestion['observation']}"),
        evidence=suggestion["evidence"],
        proposed_solution=suggestion["proposed_action"])


def scan(store: Store, owner: str = "jason") -> list[sqlite3.Row]:
    """Run every check and file new suggestions.

    Returns only the newly filed suggestion rows. Deterministic:
    scanning twice files nothing the second time unless a condition
    changed state. Makes zero provider calls and writes only to
    guardian_suggestions (plus, via the Bundle B hook, one ops
    problem report per new warning/critical suggestion).
    """
    new = []
    for check in _CHECKS:
        for finding in check(store, owner):
            row, created = _file_one(store, owner, **finding)
            if created:
                new.append(row)
                _ops_hook(store, owner, row)
    return new


def inbox(store: Store, owner: str) -> list[sqlite3.Row]:
    """Open and acknowledged suggestions, most severe first, oldest first
    within a severity. (A stale open suggestion should surface before a
    fresh one.)"""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM guardian_suggestions "
        "WHERE owner = ? AND status IN ('open', 'acknowledged') "
        "ORDER BY CASE severity "
        "           WHEN 'critical' THEN 3 "
        "           WHEN 'warning' THEN 2 "
        "           ELSE 1 END DESC, "
        "         created_at ASC, id ASC",
        (owner,)).fetchall()


def get_suggestion(store: Store, suggestion_id: int) -> sqlite3.Row | None:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE id = ?",
        (suggestion_id,)).fetchone()


def resolve(store: Store, suggestion_id: int, status: str,
            note: str = "") -> sqlite3.Row:
    """Mark a suggestion acknowledged/done/declined, with an optional note.
    Sets resolved_at. Resolving is idempotent — a later decision can
    replace an earlier one."""
    if status not in _RESOLUTIONS:
        raise BadResolution(
            f"resolution must be one of {_RESOLUTIONS}, got {status!r}")
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE id = ?",
        (suggestion_id,)).fetchone()
    if row is None:
        raise SuggestionNotFound(f"no suggestion with id {suggestion_id}")
    store._db.execute(
        "UPDATE guardian_suggestions SET status = ?, resolution_note = ?, "
        "resolved_at = ? WHERE id = ?",
        (status, note, _now(), suggestion_id))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE id = ?",
        (suggestion_id,)).fetchone()
