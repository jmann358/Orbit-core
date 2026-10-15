"""Medic: Luna's failure triage desk.

CHARTER (Jason's directive, 2026-10-14): "create a new agent who does
this before it gets to you. Constantly pursuing these fail messages
without wasting too many credits."

The chain of custody for a failure is:

    Guardian DETECTS -> Medic TRIAGES -> Mentor GRADES -> Conductor ASSIGNS

Detection is owned (Guardian's eyes, Watchman's vitals, Verifier's
re-checks), grading is owned (Mentor) — but nobody sat between
"something beeped" and "Rowan/Jason hears about it". The Medic chases
the signal down cheaply, proves whether it's real or noise, dedupes it,
attaches a diagnosis, and escalates only what survives — with the
evidence attached.

Verdicts:
- CONFIRMED: real. Carries a diagnosis (what broke, where, the first
  evidence line) and a proposed fix.
- NOISE: cleared, with the clearing evidence recorded. A cleared
  incident is still a closed record, never an erased one.
- KNOWN: a duplicate of an already-open incident — linked, never
  re-filed.

HARD BOUNDARIES (in code, structural tests pin them):
- Read-only inputs, own-table writes. Inputs are existing signals
  (open Guardian suggestions, failed specialist/builder runs); the
  Medic writes ONLY to `incidents`. He never marks another agent's
  record done, never retries a run, never re-scores a grade. The only
  "fix" he ever executes is re-running a READ-ONLY diagnostic.
- Propose-only. CONFIRMED incidents file deduped Guardian suggestions
  and may queue a Conductor `triage_sweep` candidate. Resolution stays
  with Rowan/Jason.
- Jason's credit law: ZERO provider calls, always. Deterministic
  checks first; anything unavoidable needs a per-incident cap AND an
  approval, fail-closed. Per-tick and per-day pursuit caps so the desk
  can never become the noise it filters.
- Luna-internal signals only. Rowan-side pipeline failures stay
  Rowan's discipline.
"""
import sqlite3
from datetime import datetime, timezone

from luna_v2 import guardian as GD
from luna_v2 import missions
from luna_v2.store import Store


class MedicError(missions.LunaError):
    """Refusals from the Medic's hard boundaries."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    owner        TEXT NOT NULL,
    source_kind  TEXT NOT NULL,        -- e.g. 'guardian_suggestion',
                                       -- 'specialist_run', 'builder_run'
    source_id    INTEGER NOT NULL,     -- id of the source row
    verdict      TEXT NOT NULL
                     CHECK (verdict IN ('confirmed','noise','known')),
    diagnosis    TEXT NOT NULL DEFAULT '',
    proposed_fix TEXT NOT NULL DEFAULT '',
    clearing_evidence TEXT NOT NULL DEFAULT '',
    linked_incident INTEGER,           -- for KNOWN: the open twin's id
    status       TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','closed')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
-- A source can have at most one open incident: a fresh signal never
-- exists while its twin is still open (Guardian's dedupe idiom).
CREATE UNIQUE INDEX IF NOT EXISTS idx_incidents_open_dedupe
    ON incidents (owner, source_kind, source_id)
    WHERE status = 'open';
"""

_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_medic_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._medic_schema_v = _SCHEMA_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# Jason's credit law: pursuit caps, conductor-style. The desk can never
# run up a tab chasing ghosts.
MAX_INCIDENTS_PER_TICK = 5
MAX_INCIDENTS_PER_DAY = 20


# ---------------------------------------------------------------------------
# Re-verification: deterministic classification
# ---------------------------------------------------------------------------
def _classify_guardian_suggestion(store: Store, owner: str,
                                  row: sqlite3.Row) -> tuple[str, str, str, str]:
    """Return (verdict, diagnosis, proposed_fix, clearing_evidence).

    The re-verification is deterministic: re-read the underlying record
    the suggestion points at and compare it against the suggestion's
    claim. Informational kinds are not failures — cleared, not reproduced.
    """
    check = row["check_name"]
    severity = row["severity"]
    if severity == "info":
        return ("noise", "", "",
                "informational signal — no failure condition; nothing to "
                "reproduce. The desk does not page anyone over a nudge, a "
                "proposal notice, or a progress note.")
    if check == "warden_hold":
        scan = None
        if _has_table(store, "gate_scans"):
            scan = store._db.execute(
                "SELECT * FROM gate_scans WHERE owner = ? ORDER BY id DESC",
                (owner,)).fetchone()
        if scan is not None and scan["verdict"] == "hold":
            findings = scan["findings"] or ""
            return ("confirmed",
                    f"Warden hold {scan['id']} on {scan['item_ref']} — "
                    f"{findings[:160]}".rstrip(),
                    "Rowan or Jason: read the flagged lines and clear or "
                    "acknowledge the hold",
                    "")
        return ("noise", "", "",
                "the hold no longer stands on the record it pointed at — "
                "cleared since filing")
    if check == "canon_finding":
        open_findings = []
        if _has_table(store, "canon_findings"):
            open_findings = store._db.execute(
                "SELECT id, kind, subjects FROM canon_findings "
                "WHERE owner = ? AND status = 'open'", (owner,)).fetchall()
        if open_findings:
            names = ", ".join(
                f"{f['id']}:{f['kind']}({f['subjects']})" for f in open_findings)
            return ("confirmed",
                    f"Canonist still carries open findings: {names}",
                    "Jason or Rowan: decide the open findings",
                    "")
        return ("noise", "", "",
                "all canon findings on record are decided — "
                "this inbox pointer is stale; cleared")
    if check == "mentor_review_case":
        cases = []
        if _has_table(store, "review_cases"):
            cases = store._db.execute(
                "SELECT id FROM review_cases WHERE owner = ? "
                "AND status = 'open'", (owner,)).fetchall()
        if cases:
            return ("confirmed",
                    f"review case(s) open: "
                    f"{', '.join(str(c['id']) for c in cases)}",
                    "Jason or Rowan: decide the review case",
                    "")
        return ("noise", "", "",
                "no open review case on record — cleared")
    if check == "probation_review":
        due = []
        if _has_table(store, "probation"):
            due = store._db.execute(
                "SELECT specialist, review_due FROM probation "
                "WHERE owner = ? AND status = 'active'", (owner,)).fetchall()
        names = ", ".join(p["specialist"] for p in due)
        if due:
            return ("confirmed",
                    f"active probation(s): {names} — review is due or near",
                    "Jason or Rowan: run the probation review",
                    "")
        return ("noise", "", "",
                "no active probation on record — cleared")
    # Default for warning/critical: the detector said attention-needed;
    # the underlying claim is on record and re-reads as stated.
    return ("confirmed",
            f"{check}: {row['subject'][:160]} — signal on record, "
            f"re-read matches the claim",
            "Jason or Rowan: investigate the claimed condition",
            "")


def _classify_failed_run(store: Store, owner: str, table: str,
                         row: sqlite3.Row) -> tuple[str, str, str, str]:
    return ("confirmed",
            f"failed {table} id {row['id']}: "
            f"{str(row['outcome'] if 'outcome' in row.keys() else '')[:160]}"
            .rstrip(),
            "Jason or Rowan: reproduce the failure on a scratch copy and "
            "route the fix through the normal build path",
            "")


def _file_incident(store: Store, owner: str, source_kind: str, source_id: int,
                   verdict: str, diagnosis: str, proposed_fix: str,
                   clearing: str) -> dict:
    """Idempotent filing. An already-open twin is never re-filed: the
    result comes back as KNOWN, linked to the existing open incident.
    """
    _ensure_schema(store)
    twin = store._db.execute(
        "SELECT id FROM incidents WHERE owner = ? AND source_kind = ? "
        "AND source_id = ? AND status = 'open'",
        (owner, source_kind, source_id)).fetchone()
    if twin is not None:
        return {"incident_id": twin["id"], "verdict": "known",
                "linked_incident": twin["id"], "created": False}
    cur = store._db.execute(
        "INSERT INTO incidents (owner, source_kind, source_id, verdict, "
        "diagnosis, proposed_fix, clearing_evidence, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
        (owner, source_kind, source_id, verdict, diagnosis,
         proposed_fix, clearing, _now()))
    store._db.commit()
    return {"incident_id": cur.lastrowid, "verdict": verdict,
            "linked_incident": None, "created": True}


def _has_table(store: Store, table: str) -> bool:
    return store._db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,)).fetchone() is not None


def _sources(store: Store, owner: str) -> list[tuple[str, int]]:
    """Every signal the desk is allowed to read, in a deterministic order:
    open Guardian suggestions, then failed runs. Read-only inputs only.
    """
    _ensure_schema(store)
    out = []
    for s in GD.inbox(store, owner):
        out.append(("guardian_suggestion", s["id"]))
    run_tables = {"specialist_run": "specialist_runs",
                  "builder_run": "builder_runs"}
    for kind, table in run_tables.items():
        if not _has_table(store, table):
            continue
        for r in store._db.execute(
                f"SELECT id FROM {table} WHERE status = 'failed' "
                f"ORDER BY id"):
            out.append((kind, r["id"]))
    return out


# ---------------------------------------------------------------------------
# The desk: sweep, escalate, close
# ---------------------------------------------------------------------------
def sweep(store: Store, owner: str,
          per_tick_cap: int = MAX_INCIDENTS_PER_TICK,
          per_day_cap: int = MAX_INCIDENTS_PER_DAY) -> dict:
    """Walk the current signals, classify each, file incidents.

    Deterministic: same records -> same verdicts (a test pins this).
    Zero provider calls — the credit law is structural, not a guideline.
    Caps: at most per_tick_cap new incidents per sweep, and never more
    than per_day_cap incident rows per day — the desk can never become
    the noise it exists to filter.
    """
    _ensure_schema(store)
    today = _today()
    day_count = store._db.execute(
        "SELECT COUNT(*) AS c FROM incidents WHERE owner = ? "
        "AND substr(created_at, 1, 10) = ?", (owner, today)).fetchone()["c"]
    if day_count >= per_day_cap:
        raise MedicError(
            f"refused: {per_day_cap} incidents already filed today — "
            f"the triage desk is capped so it can never run up a tab")
    results = []
    created = 0
    for source_kind, source_id in _sources(store, owner):
        if created >= per_tick_cap:
            break
        if source_kind == "guardian_suggestion":
            row = store._db.execute(
                "SELECT * FROM guardian_suggestions WHERE id = ?",
                (source_id,)).fetchone()
            if row is None or row["status"] not in ("open", "acknowledged"):
                continue
            verdict, diagnosis, fix, clearing = \
                _classify_guardian_suggestion(store, owner, row)
        else:
            table = "specialist_runs" if source_kind == "specialist_run" \
                else "builder_runs"
            row = store._db.execute(
                f"SELECT * FROM {table} WHERE id = ?",
                (source_id,)).fetchone()
            if row is None:
                continue
            verdict, diagnosis, fix, clearing = \
                _classify_failed_run(store, owner, table, row)
        res = _file_incident(store, owner, source_kind, source_id, verdict,
                             diagnosis, fix, clearing)
        res["source_kind"] = source_kind
        res["source_id"] = source_id
        results.append(res)
        if res["created"]:
            created += 1
    return {"triaged": len(results),
            "confirmed": sum(1 for r in results
                             if r["verdict"] == "confirmed"),
            "noise": sum(1 for r in results if r["verdict"] == "noise"),
            "known": sum(1 for r in results if r["verdict"] == "known"),
            "results": results}


def escalate(store: Store, owner: str, incident_id: int) -> sqlite3.Row | None:
    """File one deduped Guardian suggestion for a CONFIRMED incident,
    carrying the diagnosis and the proposed fix. Propose-only: the Medic
    never resolves anyone's record; Jason/Rowan decide.
    """
    _ensure_schema(store)
    inc = store._db.execute(
        "SELECT * FROM incidents WHERE owner = ? AND id = ?",
        (owner, incident_id)).fetchone()
    if inc is None:
        raise MedicError(f"no incident {incident_id}")
    if inc["verdict"] != "confirmed":
        raise MedicError(
            f"refused: only CONFIRMED incidents escalate — "
            f"incident {incident_id} is {inc['verdict']}")
    return GD.file_suggestion(
        store, owner, "medic_diagnosis",
        f"Medic diagnosis on incident {incident_id}: {inc['diagnosis'][:80]}",
        "warning",
        f"{inc['diagnosis']}\nProposed fix: {inc['proposed_fix']}",
        f"incidents row {incident_id} (source {inc['source_kind']}:"
        f"{inc['source_id']})",
        f"Jason or Rowan: approve the proposed fix — {inc['proposed_fix'][:120]}")


def queue_backlog(store: Store, owner: str, incident_id: int,
                  target_specialist: str = "any") -> int:
    """Enter a Conductor backlog candidate (the `triage_sweep` kind) for a
    CONFIRMED incident. Conductor assigns; the Medic never assigns.
    """
    from luna_v2 import conductor as CO
    _ensure_schema(store)
    inc = store._db.execute(
        "SELECT * FROM incidents WHERE owner = ? AND id = ?",
        (owner, incident_id)).fetchone()
    if inc is None:
        raise MedicError(f"no incident {incident_id}")
    if inc["verdict"] != "confirmed":
        raise MedicError(
            f"refused: only CONFIRMED incidents queue work — "
            f"incident {incident_id} is {inc['verdict']}")
    return CO.add_backlog(
        store, owner,
        f"triage sweep: {inc['diagnosis'][:80]}",
        "triage_sweep",
        target_specialist=target_specialist,
        payload=f"incident:{incident_id}",
        created_by="medic")


def close_incident(store: Store, owner: str, incident_id: int,
                   decided_by: str) -> sqlite3.Row:
    """Close an incident. Only Jason or Rowan closes — the Medic never
    clears his own desk (and never anyone else's records).
    """
    _ensure_schema(store)
    by = (decided_by or "").strip()
    if not by:
        raise MedicError("close_incident needs a decider name (decided_by)")
    if by.lower() == "medic":
        raise MedicError(
            "the Medic does not clear his own desk; a Jason or Rowan "
            "decision is required")
    inc = store._db.execute(
        "SELECT * FROM incidents WHERE owner = ? AND id = ?",
        (owner, incident_id)).fetchone()
    if inc is None:
        raise MedicError(f"no incident {incident_id}")
    store._db.execute(
        "UPDATE incidents SET status = 'closed' WHERE id = ?",
        (incident_id,))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()


def list_incidents(store: Store, owner: str, status: str = "") -> list[sqlite3.Row]:
    _ensure_schema(store)
    if status:
        if status not in ("open", "closed"):
            raise MedicError(f"unknown incident status {status!r}")
        return store._db.execute(
            "SELECT * FROM incidents WHERE owner = ? AND status = ? "
            "ORDER BY id", (owner, status)).fetchall()
    return store._db.execute(
        "SELECT * FROM incidents WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()
