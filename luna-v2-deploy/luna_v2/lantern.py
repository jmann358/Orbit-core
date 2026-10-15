"""Lantern: the prime specialist — the competitiveness campaign.

CHARTER (Jason's directive, 2026-10-14): "I want a specialist agent:
the sole intent is to get luna/orbit to be able to compete with
something like the Tolan app. It'll get the framework laid out,
through whatever stages it deems necessary, delegating work through
other bots, requesting workers when it deems necessary, holding
priority in line... they're like the mercenaries.. or like john
stewart the green lantern, suddenly thrust into a power of great
responsibility. however loyal and devoted."

Jason named him himself: "Lantern is a good name, the guiding light."

Lantern is a PRIME: not a pair of hands, a commander. He holds ONE
standing task that encompasses the broader picture — make Luna/ORBIT
competitive with best-in-class companion apps, benchmark: Tolan. He
keeps the campaign ledger: stages (each with the benchmark target it
answers and a written definition of done), gap items (what the
benchmark has that Luna lacks, with the source that proved it), and
delegation records (which specialist a piece of work was handed to).
His report is the honest standing of the campaign, in plain words.

HARD BOUNDARIES (in code, structural tests pin them):
- He plans, delegates, and inspects — he never executes the work
  himself, never approves a consequential step (Jason only). The
  campaign LEDGER half of this module stays deterministic: zero
  provider calls, zero fetches, arithmetic on his own records.
- His THINKING is separate, and it is genuinely his (Jason's
  independent-minds ruling, 2026-10-14: every agent is his own
  independent thinker, not Rowan in a new hat). think() hands his
  real campaign state to luna_v2/minds.py's consult engine, which
  spends exactly ONE broker-accounted dispatch under his written
  charter and records his authored words verbatim in mind_outputs.
  think() mutates NOTHING in the ledger: a gap, delegation, or stage
  change he proposes in his own words stays a proposal until Rowan
  or Jason files it through the APIs above.
- He cannot certify his own campaign. Closing a stage requires
  evidence text AND a verified_by name that is not 'lantern' —
  Verifier (or Jason/Rowan) grades the stage, Lantern only records
  the verdict. A stage marked done without both is refused.
- Own-table writes only: campaign_stages, campaign_gaps,
  campaign_delegations. Delegation targets must be real, registered
  specialists — he cannot hand work to invented hands.
- Priority in line is a queueing fact, not a permission: his
  delegations are records the court works from; they grant no scope
  the delegate does not already hold.

DIVIDING LINES (written for Canonist's reading):
- vs Conductor: Conductor keeps the court utilized day to day from a
  standing backlog. Lantern owns ONE campaign and its stages; his
  delegations are campaign work items, not utilization assignments.
- vs Trainer: Trainer grows Luna's capability against an authored
  reference bar. Lantern's bar is a living competitor product; his
  gaps are product/UX gaps, and closing them is build work he
  delegates — not drills.
- vs Marshal: Marshal runs one question across many specialists and
  closes the swarm. Lantern's campaign is standing and multi-stage;
  he is the war, Marshal runs battles.
- vs Headhunter: Headhunter staffs the court. Lantern was hired
  through him like everyone else (candidate, gate scan, probation).

Stdlib only. The ledger and the report are deterministic; think()
is the one deliberate exception — his words come from a live
dispatch, and are recorded so they can be audited, not reproduced.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from luna_v2 import missions
from luna_v2 import minds
from luna_v2 import specialists as SP
from luna_v2.store import Store


class LanternError(missions.LunaError):
    """Refusals from the campaign discipline."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign_stages (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    owner              TEXT NOT NULL,
    name               TEXT NOT NULL,
    benchmark_target   TEXT NOT NULL DEFAULT '',
    definition_of_done TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'planned'
                       CHECK (status IN
                              ('planned','active','blocked','done')),
    seq                INTEGER NOT NULL DEFAULT 0,
    note               TEXT NOT NULL DEFAULT '',
    evidence           TEXT NOT NULL DEFAULT '',
    verified_by        TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(owner, name)
);
CREATE TABLE IF NOT EXISTS campaign_gaps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    title      TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    source     TEXT NOT NULL DEFAULT '',
    severity   TEXT NOT NULL DEFAULT 'warning'
               CHECK (severity IN ('info','warning','critical')),
    stage_id   INTEGER,
    status     TEXT NOT NULL DEFAULT 'open'
               CHECK (status IN ('open','addressed','wontfix')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(owner, title)
);
CREATE TABLE IF NOT EXISTS campaign_delegations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    stage_id   INTEGER,
    specialist TEXT NOT NULL,
    work       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'assigned'
               CHECK (status IN
                      ('assigned','in_progress','done','dropped')),
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SCHEMA_VERSION = 1

STAGE_STATUSES = ("planned", "active", "blocked", "done")
GAP_SEVERITIES = ("info", "warning", "critical")
GAP_STATUSES = ("open", "addressed", "wontfix")
DELEGATION_STATUSES = ("assigned", "in_progress", "done", "dropped")

# Legal stage moves. 'done' is reachable only through complete_stage
# (which enforces the evidence + independent-verifier rule), never
# through set_stage_status.
_STAGE_MOVES = {
    "planned": ("active", "blocked"),
    "active": ("blocked", "planned"),
    "blocked": ("active", "planned"),
    "done": (),
}


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_lantern_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._lantern_schema_v = _SCHEMA_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def add_stage(store: Store, owner: str, name: str,
              benchmark_target: str = "", definition_of_done: str = "",
              seq: int = 0, note: str = "") -> sqlite3.Row:
    """Lay down a campaign stage. Idempotent on (owner, name): laying
    the same stage twice returns the existing row — a campaign plan is
    re-stated, never duplicated."""
    _ensure_schema(store)
    name = (name or "").strip()
    if not name:
        raise LanternError("refused: a campaign stage needs a name")
    if not (definition_of_done or "").strip():
        raise LanternError(
            "refused: a stage needs a written definition of done — "
            "'competitive' is a claim, the definition is the proof bar")
    store._db.execute(
        "INSERT INTO campaign_stages (owner, name, benchmark_target, "
        "definition_of_done, status, seq, note, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'planned', ?, ?, ?, ?) "
        "ON CONFLICT(owner, name) DO NOTHING",
        (owner, name, (benchmark_target or "").strip(),
         definition_of_done.strip(), int(seq), (note or "").strip(),
         _now(), _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM campaign_stages WHERE owner = ? AND name = ?",
        (owner, name)).fetchone()


def get_stage(store: Store, owner: str, stage_id: int) -> sqlite3.Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM campaign_stages WHERE owner = ? AND id = ?",
        (owner, stage_id)).fetchone()
    if row is None:
        raise LanternError(f"no campaign stage {stage_id}")
    return row


def list_stages(store: Store, owner: str) -> list:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM campaign_stages WHERE owner = ? "
        "ORDER BY seq, id", (owner,)).fetchall()


def set_stage_status(store: Store, owner: str, stage_id: int,
                     status: str, note: str = "") -> sqlite3.Row:
    """Move a stage between planned/active/blocked. 'done' is refused
    here on purpose — completion goes through complete_stage, which
    demands evidence and an independent verifier."""
    _ensure_schema(store)
    if status not in STAGE_STATUSES:
        raise LanternError(f"unknown stage status {status!r}")
    if status == "done":
        raise LanternError(
            "refused: stages close through complete_stage — evidence "
            "and a verifier who is not Lantern are required")
    row = get_stage(store, owner, stage_id)
    if status not in _STAGE_MOVES[row["status"]]:
        raise LanternError(
            f"refused: stage {stage_id} is {row['status']} — cannot "
            f"move to {status} (allowed: "
            f"{_STAGE_MOVES[row['status']] or 'none'})")
    store._db.execute(
        "UPDATE campaign_stages SET status = ?, note = ?, "
        "updated_at = ? WHERE id = ? AND owner = ?",
        (status, (note or "").strip() or row["note"], _now(),
         stage_id, owner))
    store._db.commit()
    return get_stage(store, owner, stage_id)


def complete_stage(store: Store, owner: str, stage_id: int,
                   evidence: str, verified_by: str) -> sqlite3.Row:
    """Close a stage. Requires written evidence AND a verifier who is
    not Lantern — he cannot certify his own campaign (Jason's rule for
    every prime: the commander records verdicts, he never grades his
    own war)."""
    _ensure_schema(store)
    evidence = (evidence or "").strip()
    if not evidence:
        raise LanternError(
            "refused: closing a stage needs evidence text — what "
            "proves the definition of done is met")
    by = (verified_by or "").strip()
    if not by:
        raise LanternError(
            "refused: closing a stage needs a verified_by name — "
            "someone other than Lantern graded it")
    if by.lower() == "lantern":
        raise LanternError(
            "refused: Lantern never certifies his own stages; "
            "Verifier, Jason, or Rowan verifies")
    row = get_stage(store, owner, stage_id)
    if row["status"] == "done":
        raise LanternError(f"refused: stage {stage_id} is already done")
    store._db.execute(
        "UPDATE campaign_stages SET status = 'done', evidence = ?, "
        "verified_by = ?, updated_at = ? WHERE id = ? AND owner = ?",
        (evidence, by, _now(), stage_id, owner))
    store._db.commit()
    return get_stage(store, owner, stage_id)


# ---------------------------------------------------------------------------
# Gaps
# ---------------------------------------------------------------------------
def add_gap(store: Store, owner: str, title: str, source: str,
            severity: str = "warning", detail: str = "",
            stage_id: int | None = None) -> sqlite3.Row:
    """Record a gap: something the benchmark has that Luna lacks.
    The source is required — a gap without evidence is an opinion,
    and the campaign runs on evidence. Idempotent on (owner, title)."""
    _ensure_schema(store)
    title = (title or "").strip()
    if not title:
        raise LanternError("refused: a gap needs a title")
    source = (source or "").strip()
    if not source:
        raise LanternError(
            "refused: a gap needs its source — where the benchmark's "
            "advantage was observed (a document, a page, a record)")
    if severity not in GAP_SEVERITIES:
        raise LanternError(
            f"severity must be one of {GAP_SEVERITIES}, got {severity!r}")
    if stage_id is not None:
        get_stage(store, owner, stage_id)
    store._db.execute(
        "INSERT INTO campaign_gaps (owner, title, detail, source, "
        "severity, stage_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?) "
        "ON CONFLICT(owner, title) DO NOTHING",
        (owner, title, (detail or "").strip(), source, severity,
         stage_id, _now(), _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM campaign_gaps WHERE owner = ? AND title = ?",
        (owner, title)).fetchone()


def list_gaps(store: Store, owner: str, status: str = "") -> list:
    _ensure_schema(store)
    if status:
        if status not in GAP_STATUSES:
            raise LanternError(f"unknown gap status {status!r}")
        return store._db.execute(
            "SELECT * FROM campaign_gaps WHERE owner = ? AND status = ? "
            "ORDER BY id", (owner, status)).fetchall()
    return store._db.execute(
        "SELECT * FROM campaign_gaps WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()


def set_gap_status(store: Store, owner: str, gap_id: int,
                   status: str) -> sqlite3.Row:
    _ensure_schema(store)
    if status not in GAP_STATUSES:
        raise LanternError(f"unknown gap status {status!r}")
    row = store._db.execute(
        "SELECT * FROM campaign_gaps WHERE owner = ? AND id = ?",
        (owner, gap_id)).fetchone()
    if row is None:
        raise LanternError(f"no campaign gap {gap_id}")
    store._db.execute(
        "UPDATE campaign_gaps SET status = ?, updated_at = ? "
        "WHERE id = ? AND owner = ?", (status, _now(), gap_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM campaign_gaps WHERE id = ?", (gap_id,)).fetchone()


# ---------------------------------------------------------------------------
# Delegations
# ---------------------------------------------------------------------------
def delegate(store: Store, owner: str, specialist: str, work: str,
             stage_id: int | None = None, note: str = "") -> sqlite3.Row:
    """Hand a piece of campaign work to a registered specialist.
    The record is the handoff — it grants the delegate no scope they
    do not already hold, and consequential work still waits on Jason
    wherever the delegate's own rules say so."""
    _ensure_schema(store)
    specialist = (specialist or "").strip().lower()
    if specialist not in SP.SPECIALISTS:
        raise LanternError(
            f"refused: no registered specialist named {specialist!r} — "
            "Lantern delegates to the court that exists")
    work = (work or "").strip()
    if not work:
        raise LanternError("refused: a delegation needs the work, in words")
    if stage_id is not None:
        get_stage(store, owner, stage_id)
    cur = store._db.execute(
        "INSERT INTO campaign_delegations (owner, stage_id, specialist, "
        "work, status, note, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'assigned', ?, ?, ?)",
        (owner, stage_id, specialist, work, (note or "").strip(),
         _now(), _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM campaign_delegations WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_delegations(store: Store, owner: str, status: str = "") -> list:
    _ensure_schema(store)
    if status:
        if status not in DELEGATION_STATUSES:
            raise LanternError(
                f"unknown delegation status {status!r}")
        return store._db.execute(
            "SELECT * FROM campaign_delegations WHERE owner = ? "
            "AND status = ? ORDER BY id", (owner, status)).fetchall()
    return store._db.execute(
        "SELECT * FROM campaign_delegations WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()


def set_delegation_status(store: Store, owner: str, delegation_id: int,
                          status: str, note: str = "") -> sqlite3.Row:
    _ensure_schema(store)
    if status not in DELEGATION_STATUSES:
        raise LanternError(f"unknown delegation status {status!r}")
    row = store._db.execute(
        "SELECT * FROM campaign_delegations WHERE owner = ? AND id = ?",
        (owner, delegation_id)).fetchone()
    if row is None:
        raise LanternError(f"no campaign delegation {delegation_id}")
    store._db.execute(
        "UPDATE campaign_delegations SET status = ?, note = ?, "
        "updated_at = ? WHERE id = ? AND owner = ?",
        (status, (note or "").strip() or row["note"], _now(),
         delegation_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM campaign_delegations WHERE id = ?",
        (delegation_id,)).fetchone()


# ---------------------------------------------------------------------------
# The report: the campaign's honest standing, in plain words
# ---------------------------------------------------------------------------
def campaign_report(store: Store, owner: str) -> str:
    """Deterministic: the same ledger always renders the same report.
    Zero provider calls — arithmetic on the campaign's own records."""
    _ensure_schema(store)
    lines = ["LANTERN CAMPAIGN — Luna vs the best-in-class benchmark "
             "(Tolan)."]
    stages = list_stages(store, owner)
    if stages:
        lines.append("Stages:")
        for s in stages:
            lines.append(f"  {s['seq']}. [{s['status']}] {s['name']} — "
                         f"target: {s['benchmark_target']}")
            lines.append(f"     done when: {s['definition_of_done']}")
            if s["status"] == "done":
                lines.append(f"     evidence: {s['evidence']} "
                             f"(verified by {s['verified_by']})")
            if s["note"]:
                lines.append(f"     note: {s['note']}")
    else:
        lines.append("No campaign stages laid out yet.")
    gaps = list_gaps(store, owner, "open")
    if gaps:
        by_sev = {sev: 0 for sev in GAP_SEVERITIES}
        for g in gaps:
            by_sev[g["severity"]] += 1
        lines.append(
            f"Open gaps: {len(gaps)} (critical {by_sev['critical']}, "
            f"warning {by_sev['warning']}, info {by_sev['info']})")
        stage_names = {s["id"]: s["name"] for s in stages}
        for g in gaps:
            where = (f" — stage: {stage_names[g['stage_id']]}"
                     if g["stage_id"] in stage_names else "")
            lines.append(f"  [{g['severity']}] {g['title']} "
                         f"(source: {g['source']}){where}")
    else:
        lines.append("Open gaps: none recorded.")
    open_del = [d for d in list_delegations(store, owner)
                if d["status"] in ("assigned", "in_progress")]
    if open_del:
        lines.append(f"Open delegations: {len(open_del)}")
        for d in open_del:
            lines.append(f"  {d['specialist']}: {d['work']} "
                         f"[{d['status']}]")
    else:
        lines.append("Open delegations: none.")
    blocked = [s for s in stages if s["status"] == "blocked"]
    if blocked:
        lines.append("Blocked stages (waiting on Jason or an outside "
                     "fact):")
        for s in blocked:
            lines.append(f"  {s['name']}"
                         + (f" — {s['note']}" if s["note"] else ""))
    else:
        lines.append("Blocked on Jason: nothing right now.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# His own thinking (Jason's independent-minds ruling, 2026-10-14)
# ---------------------------------------------------------------------------
THINK_TASK = (
    "Review your campaign. Name the single highest-leverage next "
    "action, any gap the records imply but don't yet list, and "
    "anything you would ask Jason — in your own words, under your "
    "charter.")


def think(store: Store, owner: str, *, transport=None,
          mission_id: int | None = None):
    """Lantern reviews his own campaign and speaks for himself.

    The context is his REAL campaign state — the same ledger the
    deterministic report renders (stages, open gaps with severities,
    open delegations, the blocked-on-Jason line) — and the thinking
    is one broker-accounted dispatch through minds.consult, under
    his charter. His words come back verbatim and are recorded in
    mind_outputs; this function reads the ledger and changes none of
    it. Test-pinned: the think path cannot call a single stage, gap,
    or delegation mutation.
    """
    context = campaign_report(store, owner)
    return minds.consult(store, "lantern", THINK_TASK, context,
                         transport=transport, mission_id=mission_id,
                         owner=owner)
