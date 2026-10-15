"""Conductor: the anti-idle coordinator.

Scheduler works by the clock; Conductor works by IDLENESS. It watches which
specialists have done nothing, keeps a backlog of useful routine work, and
assigns it to the most idle eligible specialist — always inside their
existing scopes and budgets.

Conductor does no specialist work itself and grants nothing.

Jason's charter change (2026-10-14): Conductor MAY invent work — but only
work productive enough to be worth it. Invention is state-driven: it reads
real state (stale receipts, hot allocations, stale grades, rotation gaps)
and each invented item carries a mandatory one-sentence value_case naming
the concrete payoff. Nothing is invented without a stated reason, invented
items never jump the standing queue, and an honest "nothing worth
inventing" is a valid answer.

Rules of conduct:
- 'retired' specialists (Mentor's review system) are never assigned.
- 'restricted' specialists may only take 'training' work.
- Invented items enter with priority NO BETTER than the lowest standing
  priority, at most MAX_INVENTED_OPEN invented items may be open at once,
  and a tick assigns at most INVENTED_PER_TICK invented item.
- Built-in kinds execute deterministic module calls immediately; the rest
  become real missions with routine steps only (never consequential).
- At most DAILY_CAP assignments per owner per UTC day.
- Zero provider calls; Conductor only records.
"""
import json
import math
import sqlite3
from datetime import datetime, timezone

from luna_v2.store import Store
from luna_v2.missions import LunaError

BACKLOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_backlog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    title           TEXT NOT NULL,
    kind            TEXT NOT NULL,
    target_specialist TEXT NOT NULL DEFAULT 'any',
    payload         TEXT NOT NULL DEFAULT '',
    priority        INTEGER NOT NULL DEFAULT 5,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','assigned','done','dropped')),
    created_by      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (owner, title)
);
"""

ASSIGNMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    backlog_id  INTEGER NOT NULL REFERENCES work_backlog(id),
    specialist  TEXT NOT NULL,
    how         TEXT NOT NULL CHECK (how IN ('builtin','mission')),
    mission_id  INTEGER,
    outcome     TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    assigned_at TEXT NOT NULL
);
"""

# Built-in kinds: executed as deterministic module calls, immediately.
BUILTIN_KINDS = ("health_check", "guardian_scan", "qm_report",
                 "sentinel_audit", "verify_recent", "mentor_grades",
                 "project_tick", "canon_sweep", "arbiter_audit",
                 "outrider_report")
# Mission kinds: become real routine-step missions for the assignee.
MISSION_KINDS = ("training", "research", "tidy", "design", "scan",
                 "talent_hunt", "threat_sweep", "experiment",
                 "web_mission", "swarm", "memory_mining",
                 "research_campaign", "red_team", "training_plan",
                 "triage_sweep")
VALID_KINDS = BUILTIN_KINDS + MISSION_KINDS
VALID_STATUSES = ("open", "assigned", "done", "dropped")

# Natural owner for each built-in kind when target_specialist == 'any'.
BUILTIN_OWNER = {
    "health_check": "watchman",
    "guardian_scan": "guardian",
    "qm_report": "quartermaster",
    "sentinel_audit": "sentinel",
    "verify_recent": "verifier",
    "mentor_grades": "mentor",
    "project_tick": "steward",
    "canon_sweep": "canonist",
    "arbiter_audit": "arbiter",
    "outrider_report": "outrider",
}

# Natural owner for mission kinds with a standing specialist of record.
MISSION_OWNER = {
    "talent_hunt": "headhunter",
    "threat_sweep": "taster",
    "experiment": "alchemist",
    "web_mission": "pathfinder",
    "swarm": "marshal",
    "memory_mining": "weaver",
    "research_campaign": "cartographer",
    "red_team": "jester",
}

# Mission kinds that need a human-ish reading of the request; if no target
# is named, they go to the most idle eligible specialist.
DAILY_CAP = 6

# Invention discipline (Jason's charter): invented work is the lowest
# rung of the backlog — it never jumps standing/jason/rowan work.
VALID_ORIGINS = ("standing", "jason", "rowan", "invented")
MAX_INVENTED_OPEN = 2
INVENTED_PER_TICK = 1


class ConductorError(LunaError):
    """Base error for the Conductor."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(BACKLOG_SCHEMA)
    store._db.execute(ASSIGNMENTS_SCHEMA)
    # Additive migration: provenance + worth case (existing rows read as
    # 'standing'; the charter change is backward-compatible).
    existing = {r["name"] for r in store._db.execute(
        "PRAGMA table_info(work_backlog)").fetchall()}
    if "origin" not in existing:
        store._db.execute(
            "ALTER TABLE work_backlog ADD COLUMN origin "
            "TEXT NOT NULL DEFAULT 'standing'")
    if "value_case" not in existing:
        store._db.execute(
            "ALTER TABLE work_backlog ADD COLUMN value_case "
            "TEXT NOT NULL DEFAULT ''")
    store._db.commit()


def _validate_kind(kind: str) -> None:
    if kind not in VALID_KINDS:
        raise ConductorError(
            f"unknown backlog kind {kind!r} "
            f"(known: {', '.join(VALID_KINDS)})")


# ---------------------------------------------------------------------------
# Backlog
# ---------------------------------------------------------------------------
def add_backlog(store: Store, owner: str, title: str, kind: str, *,
                target_specialist: str = "any", payload: str = "",
                priority: int = 5, created_by: str = "",
                origin: str = "standing", value_case: str = "") -> int:
    """Add one backlog item. Idempotent on (owner, title): re-adding with the
    same title updates the row instead of duplicating it (status untouched).

    Charter rule: invented items REQUIRE a value_case naming the concrete
    payoff. An invention without a stated worth-it case is refused at
    insert — it never enters the backlog."""
    from luna_v2 import specialists as SP

    title = (title or "").strip()
    if not title:
        raise ConductorError("backlog title is required")
    _validate_kind(kind)
    if origin not in VALID_ORIGINS:
        raise ConductorError(
            f"unknown backlog origin {origin!r} "
            f"(known: {', '.join(VALID_ORIGINS)})")
    value_case = (value_case or "").strip()
    if origin == "invented" and not value_case:
        raise ConductorError(
            "invented backlog items need a value_case naming the payoff — "
            "nothing is invented without a stated worth-it case")
    if target_specialist != "any":
        SP.get_profile(target_specialist)  # raises SpecialistNotFound
    now = _now()
    _ensure_schema(store)
    store._db.execute(
        """INSERT INTO work_backlog
           (owner, title, kind, target_specialist, payload, priority,
            status, created_by, origin, value_case, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
           ON CONFLICT (owner, title) DO UPDATE SET
             kind = excluded.kind,
             target_specialist = excluded.target_specialist,
             payload = excluded.payload,
             priority = excluded.priority,
             created_by = excluded.created_by,
             origin = excluded.origin,
             value_case = excluded.value_case,
             updated_at = excluded.updated_at""",
        (owner, title, kind, target_specialist, payload, priority,
         created_by, origin, value_case, now, now))
    # lastrowid is unreliable after an upsert; always re-read the row.
    row = store._db.execute(
        "SELECT id FROM work_backlog WHERE owner = ? AND title = ?",
        (owner, title)).fetchone()
    store._db.commit()
    return row["id"]


def list_backlog(store: Store, owner: str, *,
                 status: str = "open") -> list:
    """Open backlog first-class; priority ASC then oldest first."""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM work_backlog WHERE owner = ? AND status = ? "
        "ORDER BY priority ASC, created_at ASC, id ASC",
        (owner, status)).fetchall()


def drop_backlog(store: Store, owner: str, backlog_id: int) -> None:
    """Mark one backlog item dropped (never deleted)."""
    _ensure_schema(store)
    cur = store._db.execute(
        "UPDATE work_backlog SET status = 'dropped', updated_at = ? "
        "WHERE owner = ? AND id = ? AND status = 'open'",
        (_now(), owner, backlog_id))
    store._db.commit()
    if not cur.rowcount:
        raise ConductorError(
            f"no open backlog item {backlog_id} for owner {owner!r}")


def seed_backlog(store: Store, owner: str) -> list[int]:
    """Standing routine work. Idempotent (titles are unique per owner)."""
    _ensure_schema(store)
    seeds = [
        ("Re-verify the latest receipts", "verify_recent", "any", 3),
        ("Team health deep check", "health_check", "any", 2),
        ("Persist Mentor grades", "mentor_grades", "any", 3),
        ("Warden self-scan set", "scan", "warden", 4),
        ("Training rotation scenario", "training", "any", 5),
        ("Hunt expiring free allocations", "research", "scout", 6),
    ]
    return [add_backlog(store, owner, title, kind,
                        target_specialist=target, priority=pri,
                        created_by="conductor-seed")
            for title, kind, target, pri in seeds]


# ---------------------------------------------------------------------------
# Idleness
# ---------------------------------------------------------------------------
def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def idleness(store: Store, owner: str) -> list[dict]:
    """Per registered specialist: effective status, last real activity, and
    days idle. Activity sources: specialist_runs + builder_runs timestamps
    and mentor_grades graded_at (grading is a recorded outcome of work).
    A specialist that never ran anything is the most idle of all."""
    from luna_v2 import specialists as SP
    from luna_v2 import builder as BU
    from luna_v2 import mentor as MT

    _ensure_schema(store)
    SP._ensure_schema(store)
    BU._ensure_schema(store)
    MT._ensure_schema(store)
    now = datetime.now(timezone.utc)
    run_last = {
        r["specialist"]: _parse_ts(r["last_at"]) or None
        for r in store._db.execute(
            "SELECT specialist, MAX(created_at) AS last_at "
            "FROM specialist_runs WHERE owner = ? "
            "GROUP BY specialist", (owner,)).fetchall()}
    for r in store._db.execute(
            "SELECT MAX(created_at) AS last_at FROM builder_runs "
            "WHERE owner = ?", (owner,)).fetchall():
        ts = _parse_ts(r["last_at"]) or None
        prev = run_last.get("builder")
        if ts is not None and (prev is None or ts > prev):
            run_last["builder"] = ts
    grade_last = {
        r["specialist"]: _parse_ts(r["graded_at"]) or None
        for r in store._db.execute(
            "SELECT specialist, MAX(graded_at) AS graded_at "
            "FROM mentor_grades WHERE owner = ? "
            "GROUP BY specialist", (owner,)).fetchall()}

    board = []
    for profile in SP.list_specialists():
        ts_candidates = [t for t in (run_last.get(profile.name),
                                     grade_last.get(profile.name))
                         if t is not None]
        last = max(ts_candidates) if ts_candidates else None
        days_idle = (now - last).total_seconds() / 86400.0 if last else None
        board.append({
            "specialist": profile.name,
            "title": profile.title,
            "effective_status": SP.effective_status(store, owner,
                                                   profile.name),
            "last_activity": last.isoformat() if last else None,
            "days_idle": days_idle,  # None == never ran: most idle
        })
    # Ascending: never-ran maps to -1, so the most idle comes first.
    board.sort(key=lambda r: (-1.0 if r["days_idle"] is None
                              else r["days_idle"]))
    return board


def _eligible(store, owner, name, kind, target) -> bool:
    """Retired specialists are never assigned; restricted ones may only
    take training work. The Conductor itself is never a worker: it
    coordinates, it does not do specialist work."""
    from luna_v2 import specialists as SP

    if name == "conductor":
        return False
    if target != "any" and name != target:
        return False
    status = SP.effective_status(store, owner, name)
    if status == "retired":
        return False
    if status == "restricted" and kind != "training":
        return False
    return True


def most_idle(store: Store, owner: str, kind: str, *,
              target: str = "any") -> dict | None:
    """The most idle eligible specialist for this work, or None."""
    for row in idleness(store, owner):
        if _eligible(store, owner, row["specialist"], kind, target):
            return row
    return None


# ---------------------------------------------------------------------------
# Built-in execution
# ---------------------------------------------------------------------------
def _run_health_check(store, owner) -> str:
    from luna_v2 import watchman as W
    rep = W.health_check(store, owner)
    return (f"health {rep['status']} "
            f"(report {rep['report_id']}, "
            f"{len(rep['checks'])} checks)")


def _run_guardian_scan(store, owner) -> str:
    from luna_v2 import guardian as G
    rows = G.scan(store, owner)
    open_now = [r for r in rows if r["status"] == "open"]
    return (f"{len(open_now)} open suggestion(s) "
            f"after scan ({len(rows)} total rows)")


def _run_qm_report(store, owner) -> str:
    from luna_v2 import quartermaster as QM
    rep = QM.report(store, owner)
    flagged = sum(1 for a in rep["allocations"] if a["flags"])
    return (f"{len(rep['allocations'])} allocation(s), "
            f"{flagged} flagged")


def _run_sentinel_audit(store, owner) -> str:
    from luna_v2 import sentinel as S
    findings = S.audit(store, owner)
    worst = "clear"
    for sev in ("critical", "warning", "info"):
        if any(f["severity"] == sev for f in findings):
            worst = sev
            break
    return (f"{len(findings)} finding(s), worst severity {worst}")


def _run_verify_recent(store, owner, payload: str = "") -> str:
    from luna_v2 import verifier as V
    target = None
    if payload:
        try:
            target = json.loads(payload).get("mission_id")
        except (ValueError, AttributeError):
            target = None
    if target is None:
        row = store._db.execute(
            "SELECT m.id FROM missions m JOIN receipts r "
            "ON r.mission_id = m.id "
            "WHERE m.owner = ? AND m.status = 'closed' "
            "ORDER BY m.id DESC LIMIT 1", (owner,)).fetchone()
        target = row["id"] if row else None
    if target is None:
        return "no closed missions with receipts to verify"
    res = V.verify_mission(store, target, owner=owner)
    return (f"mission {target} re-verified: "
            f"{res.verdict} (run {res.run_id})")


def _run_mentor_grades(store, owner) -> str:
    from luna_v2 import mentor as MT
    res = MT.persist_grades(store, owner)
    return (f"graded {res['graded']} runs, "
            f"persisted {res['persisted_new']} new")


def _run_project_tick(store, owner) -> str:
    from luna_v2 import steward as ST
    res = ST.nudge_check(store, owner)
    return (f"nudge check: {res['nudged_projects']} project(s) with due "
            f"questions, {res['suggestions_filed']} suggestion(s) filed")


def _run_canon_sweep(store, owner) -> str:
    from luna_v2 import canonist as CN
    res = CN.sweep(store, owner)
    return (f"canon sweep: {res['new_findings']} new finding(s), "
            f"{res['guardian_suggestions_filed']} suggestion(s) filed")


def _run_arbiter_audit(store, owner) -> str:
    from luna_v2 import arbiter as AB
    res = AB.audit_windows(store, owner)
    return (f"arbiter audit: {res['checked']} window(s) checked, "
            f"{res['too_short']} too short, {res['new_findings']} new "
            f"finding(s), {res['guardian_suggestions_filed']} "
            f"suggestion(s) filed")


def _run_outrider_report(store, owner) -> str:
    from luna_v2 import outrider as OU
    watch = OU.list_watchlist(store, owner)
    obs = OU.list_observations(store, owner)
    due = OU.refresh_due(store, owner)
    return (f"outrider report: watching {len(watch)} rival(s), "
            f"{len(obs)} observation(s) on the books, "
            f"{len(due)} refresh(es) due")


BUILTIN_RUNNERS = {
    "health_check": (_run_health_check, "watchman"),
    "guardian_scan": (_run_guardian_scan, "guardian"),
    "qm_report": (_run_qm_report, "quartermaster"),
    "sentinel_audit": (_run_sentinel_audit, "sentinel"),
    "verify_recent": (_run_verify_recent, "verifier"),
    "mentor_grades": (_run_mentor_grades, "mentor"),
    "project_tick": (_run_project_tick, "steward"),
    "canon_sweep": (_run_canon_sweep, "canonist"),
    "arbiter_audit": (_run_arbiter_audit, "arbiter"),
    "outrider_report": (_run_outrider_report, "outrider"),
}


def _execute_builtin(store, owner, kind, specialist,
                   payload: str = "") -> str:
    """Run the deterministic module call; return a one-line outcome.
    Honest errors are recorded, never swallowed silently. The payload lets
    an invented item aim the runner (e.g. verify_recent at the stale
    mission instead of the latest)."""
    runner, natural = BUILTIN_RUNNERS[kind]
    try:
        if kind == "verify_recent":
            return f"ok: {runner(store, owner, payload)}"
        return f"ok: {runner(store, owner)}"
    except Exception as exc:  # noqa: BLE001 - recorded, not hidden
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return f"error: {first}"


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------
def _today_assignment_count(store: Store, owner: str) -> int:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT COUNT(*) AS n FROM assignments "
        "WHERE owner = ? AND date(assigned_at) = date('now')",
        (owner,)).fetchone()
    return row["n"]


def _record_assignment(store, owner, backlog_id, specialist, how,
                       outcome, reason, mission_id=None) -> None:
    store._db.execute(
        "INSERT INTO assignments (owner, backlog_id, specialist, how, "
        "mission_id, outcome, reason, assigned_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (owner, backlog_id, specialist, how, mission_id,
         outcome, reason, _now()))
    store._db.commit()


def _create_work_mission(store, owner, item, specialist) -> int:
    """A mission-kind backlog item becomes a real mission with ROUTINE
    steps only — the assignee's scope still governs what they may do."""
    from luna_v2 import missions as MS
    from luna_v2.missions import ROUTINE

    mission = MS.create_mission(
        store, owner,
        title=f"Conductor: {item['title']} ({specialist})",
        outcome=f"Assigned by Conductor from backlog item {item['id']} "
                f"to {specialist}.")
    steps = [
        f"Do the {item['kind']} work described in the backlog payload"
        + (f": {item['payload']}" if item["payload"] else
           f" for '{item['title']}'"),
        "Record evidence of what was done on the relevant step(s)",
        "Report back so Conductor can mark the assignment complete",
    ]
    for desc in steps:
        MS.add_step(store, owner, mission.id, desc, kind=ROUTINE)
    return mission.id


def _pulse_tick(store: Store, owner: str, report: dict) -> None:
    """Bundle B: every tick lands one pulse event in the ops feed —
    deterministic text: what the tick assigned (specialist, title,
    outcome) and what it skipped, plus the note when nothing moved."""
    from luna_v2 import ops as OPS
    assigned = report["assigned"]
    summary = (f"conductor tick: {len(assigned)} assigned, "
               f"{len(report['skipped'])} skipped")
    if assigned:
        summary += " — " + "; ".join(
            f"{a['specialist']}: {a['title']} ({a['outcome']})"
            for a in assigned)
    if report["note"]:
        summary += f" — {report['note']}"
    OPS.emit_pulse(store, owner, "done", "conductor", summary,
                   ref="conductor-tick")


def tick(store: Store, owner: str, *,
         max_assignments: int = 3) -> dict:
    """Assign open backlog work to the most idle eligible specialists.

    Returns {"assigned": [...], "skipped": [...], "note": str}. Never
    invents busywork: an empty backlog, an empty roster, or no eligible
    specialist means zero assignments, said plainly."""
    _ensure_schema(store)
    report = {"assigned": [], "skipped": [], "note": ""}
    remaining = min(max_assignments, DAILY_CAP - _today_assignment_count(
        store, owner))
    if remaining <= 0:
        report["note"] = (
            f"daily cap reached ({DAILY_CAP}/day); nothing assigned")
        _pulse_tick(store, owner, report)
        return report

    invented_assigned = 0
    for item in list_backlog(store, owner):
        if remaining <= 0:
            break
        origin = item["origin"] or "standing"
        # Charter: invented work never outranks standing/jason/rowan work —
        # it is queued behind by priority, and a tick assigns at most one.
        if origin == "invented" and invented_assigned >= INVENTED_PER_TICK:
            report["skipped"].append(
                {"backlog_id": item["id"], "title": item["title"],
                 "reason": f"invented cap ({INVENTED_PER_TICK}/tick) — "
                          "standing work first"})
            continue
        kind = item["kind"]
        # Built-in kinds go to their natural owner when no target is
        # named; mission kinds with no target go to the most idle agent.
        target = item["target_specialist"]
        if target == "any" and kind in BUILTIN_OWNER:
            target = BUILTIN_OWNER[kind]
        elif target == "any" and kind in MISSION_OWNER:
            target = MISSION_OWNER[kind]
        chosen = most_idle(store, owner, kind, target=target)
        if chosen is None:
            report["skipped"].append(
                {"backlog_id": item["id"], "title": item["title"],
                 "reason": "no eligible specialist "
                          "(all retired, or target restricted)"})
            continue
        name = chosen["specialist"]
        if origin == "invented":
            invented_assigned += 1
        if kind in BUILTIN_RUNNERS:
            outcome = _execute_builtin(store, owner, kind, name,
                                       item["payload"])
            _record_assignment(store, owner, item["id"], name, "builtin",
                               outcome, f"{kind} executed by {name}")
            store._db.execute(
                "UPDATE work_backlog SET status = 'done', updated_at = ? "
                "WHERE id = ?", (_now(), item["id"]))
            store._db.commit()
            report["assigned"].append(
                {"backlog_id": item["id"], "title": item["title"],
                 "specialist": name, "how": "builtin",
                 "outcome": outcome})
        else:
            mission_id = _create_work_mission(store, owner, item, name)
            _record_assignment(
                store, owner, item["id"], name, "mission",
                f"mission {mission_id} created",
                f"{kind} mission assigned to {name}", mission_id)
            store._db.execute(
                "UPDATE work_backlog SET status = 'assigned', "
                "updated_at = ? WHERE id = ?", (_now(), item["id"]))
            store._db.commit()
            report["assigned"].append(
                {"backlog_id": item["id"], "title": item["title"],
                 "specialist": name, "how": "mission",
                 "outcome": f"mission {mission_id} created"})
        remaining -= 1

    if not report["assigned"] and not report["skipped"]:
        report["note"] = "backlog is empty — nothing assigned"
    elif not report["assigned"]:
        report["note"] = ("no eligible specialist for any open item — "
                          "nothing assigned")
    _pulse_tick(store, owner, report)
    return report


def recent_assignments(store: Store, owner: str, *,
                       limit: int = 20) -> list:
    """Newest assignments first. Origin rides along via the backlog join —
    the assignments table itself records nothing extra."""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT a.*, w.origin AS origin, w.value_case AS value_case "
        "FROM assignments a LEFT JOIN work_backlog w "
        "ON w.id = a.backlog_id "
        "WHERE a.owner = ? "
        "ORDER BY a.id DESC LIMIT ?", (owner, limit)).fetchall()


# ---------------------------------------------------------------------------
# Invention — Jason's charter: only work productive enough to be worth it.
# ---------------------------------------------------------------------------
def _recently_invented(store: Store, owner: str, dedupe: str) -> bool:
    """The same pattern+target is already open, or was assigned in the last
    7 days — inventing again would be a duplicate, not new work."""
    _ensure_schema(store)
    rows = store._db.execute(
        """SELECT id FROM work_backlog
           WHERE owner = ? AND payload LIKE ?
             AND (status IN ('open', 'assigned')
                  OR (status = 'done'
                      AND updated_at >= datetime('now', '-7 days')))""",
        (owner, f'%"dedupe": "{dedupe}"%')).fetchall()
    return bool(rows)


def _open_invented_count(store: Store, owner: str) -> int:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT COUNT(*) AS n FROM work_backlog "
        "WHERE owner = ? AND origin = 'invented' AND status = 'open'",
        (owner,)).fetchone()
    return row["n"]


def _invented_priority(store: Store, owner: str) -> int:
    """Invented items take the WORST standing priority: they queue behind
    every standing/jason/rowan item, never ahead of any of them."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT MAX(priority) AS worst FROM work_backlog "
        "WHERE owner = ? AND origin != 'invented' AND status = 'open'",
        (owner,)).fetchone()
    return row["worst"] if row["worst"] is not None else 5


def _invent_stale_verification(store, owner) -> list:
    """(a) Receipted missions never re-verified since their receipt —
    oldest first. Each is its own candidate (caps still bound the run)."""
    from luna_v2 import verifier as V

    V._ensure_schema(store)
    cands = []
    for row in store._db.execute(
            """SELECT m.id AS mission_id FROM missions m
               JOIN receipts r ON r.mission_id = m.id
               WHERE m.owner = ? AND m.status = 'closed'
                 AND NOT EXISTS (
                     SELECT 1 FROM verification_runs v
                     WHERE v.mission_id = m.id
                       AND v.created_at >= r.created_at)
               ORDER BY m.id ASC""", (owner,)).fetchall():
        mid = row["mission_id"]
        cands.append({
            "pattern": "stale-verification",
            "dedupe": f"mission:{mid}",
            "title": f"Invented {_today()}: re-verify mission {mid} "
                     "(receipt stale)",
            "kind": "verify_recent",
            "target": "verifier",
            "payload": {"mission_id": mid},
            "value_case": (
                f"Mission {mid} has never been re-verified since its "
                "receipt — catching a silent inconsistency now beats "
                "finding it after it compounds."),
        })
    return cands


def _invent_allocation_risk(store, owner) -> dict | None:
    """(b) An allocation ≥80% consumed, or a use-or-lose one expiring soon."""
    from luna_v2 import broker as B

    now = datetime.now(timezone.utc)
    cands = []
    for a in B.list_allocations(store, owner, now):
        if not getattr(a, "routable", False):
            continue
        allowance = a.allowance or 0.0
        pct = (a.used / allowance * 100.0) if allowance else 0.0
        days_left = (a.resets_in.total_seconds() / 86400.0
                     if a.resets_in is not None else None)
        if pct >= 80.0:
            tag = "burn"
            value_case = (
                f"{a.provider} {a.unit} allocation is {pct:.0f}% consumed "
                "— a use-before-reset check now can re-route work or "
                "tighten dispatch caps before it runs dry mid-mission.")
        elif (days_left is not None and days_left <= 7.0 and pct < 50.0):
            tag = "use-or-lose"
            value_case = (
                f"{a.provider} {a.unit} allocation resets in "
                f"{days_left:.1f} day(s) with only {pct:.0f}% used — "
                "route extra work there before free capacity evaporates.")
        else:
            continue
        cands.append({
            "pattern": "allocation-risk",
            "dedupe": f"alloc:{tag}:{a.provider}:{a.unit}",
            "title": f"Invented {_today()}: {a.provider} {a.unit} "
                     f"{tag} check",
            "kind": "research",
            "target": "scout",
            "payload": {},
            "value_case": value_case,
        })
    return cands


def _invent_grade_gap(store, owner) -> dict | None:
    """(c) Runs exist but no Mentor grade in the last 14 days."""
    from luna_v2 import mentor as MT
    from luna_v2 import specialists as SP
    from luna_v2 import builder as BU

    SP._ensure_schema(store)
    MT._ensure_schema(store)
    BU._ensure_schema(store)
    runners = {r["specialist"] for r in store._db.execute(
        "SELECT DISTINCT specialist FROM specialist_runs "
        "WHERE owner = ?", (owner,)).fetchall()}
    if store._db.execute(
            "SELECT 1 FROM builder_runs WHERE owner = ? LIMIT 1",
            (owner,)).fetchone():
        runners.add("builder")
    graded = {r["specialist"] for r in store._db.execute(
        "SELECT DISTINCT specialist FROM mentor_grades WHERE owner = ? "
        "AND graded_at >= datetime('now', '-14 days')", (owner,)).fetchall()}
    cands = []
    for name in sorted(runners - graded):
        cands.append({
            "pattern": "grade-gap",
            "dedupe": f"grade:{name}",
            "title": f"Invented {_today()}: refresh Mentor grades "
                     "(stale review evidence)",
            "kind": "mentor_grades",
            "target": "mentor",
            "payload": {},
            "value_case": (
                f"{name} has real runs but no Mentor grade in the last "
                "14 days — review cases need fresh grades to stay fair."),
        })
    return cands


def _invent_rotation_gap(store, owner) -> dict | None:
    """(d) A specialist that has never run: rotation coverage for Jason's
    mandatory-training doctrine."""
    from luna_v2 import specialists as SP

    cands = []
    board = idleness(store, owner)
    for row in board:
        name = row["specialist"]
        if name == "conductor" or row["days_idle"] is not None:
            continue
        if SP.effective_status(store, owner, name) == "retired":
            continue
        cands.append({
            "pattern": "rotation-gap",
            "dedupe": f"rotation:{name}",
            "title": f"Invented {_today()}: training rotation for {name}",
            "kind": "training",
            "target": name,
            "payload": {},
            "value_case": (
                "Rotation coverage under Jason's mandatory-training "
                f"doctrine: {name} has never exercised its scope in a "
                "real run."),
        })
    return cands


_INVENT_PATTERNS = (
    ("stale-verification", _invent_stale_verification),
    ("allocation-risk", _invent_allocation_risk),
    ("grade-gap", _invent_grade_gap),
    ("rotation-gap", _invent_rotation_gap),
)


def invent_work(store: Store, owner: str, limit: int = 2) -> dict:
    """Scan real state for productive patterns and turn the best into
    backlog items — each with a mandatory value_case. Never invents
    busywork: a pattern that finds nothing says so, an empty worth-it
    case is refused, and 'nothing worth inventing right now' is an
    honest outcome.

    Returns {"invented": [...], "skipped": [...], "note": str}."""
    _ensure_schema(store)
    result: dict = {"invented": [], "skipped": [], "note": ""}
    invented_priority = _invented_priority(store, owner)

    for tag, fn in _INVENT_PATTERNS:
        cands = fn(store, owner)
        if not cands:
            result["skipped"].append({
                "pattern": tag,
                "reason": _clean_reason_for(tag)})
            continue
        for cand in cands:
            if not cand["value_case"].strip():
                # Worth-it enforcement: no case, no invention.
                result["skipped"].append(
                    {"pattern": tag,
                     "reason": "no value case stated — invention refused"})
                continue
            if _recently_invented(store, owner, cand["dedupe"]):
                result["skipped"].append(
                    {"pattern": tag,
                     "reason": f"already open or assigned in the last 7 "
                               f"days ({cand['title']})"})
                continue
            if _open_invented_count(store, owner) >= MAX_INVENTED_OPEN:
                result["skipped"].append(
                    {"pattern": tag,
                     "reason": f"max {MAX_INVENTED_OPEN} invented items "
                               "already open — further invention waits"})
                continue
            if len(result["invented"]) >= limit:
                result["skipped"].append(
                    {"pattern": tag,
                     "reason": f"invent limit reached ({limit})"})
                continue
            payload = {"pattern": tag, "dedupe": cand["dedupe"]}
            payload.update(cand.get("payload", {}))
            bid = _invent_or_reopen(
                store, owner, cand, json.dumps(payload),
                invented_priority)
            result["invented"].append({
                "backlog_id": bid,
                "title": cand["title"],
                "kind": cand["kind"],
                "target": cand["target"],
                "value_case": cand["value_case"],
                "pattern": tag,
            })

    if not result["invented"]:
        result["note"] = ("nothing worth inventing right now — every "
                          "pattern came back clean")
    return result


def _invent_or_reopen(store: Store, owner: str, cand: dict,
                      payload: str, priority: int) -> int:
    """File the invention. Same-day re-invention is idempotent (the open
    row is simply refreshed). A legitimate re-invention after the 7-day
    dedupe window RE-OPENS the original row with fresh fields — history
    stays append-only, nothing is deleted or duplicated."""
    row = store._db.execute(
        "SELECT id, status FROM work_backlog WHERE owner = ? AND title = ?",
        (owner, cand["title"])).fetchone()
    if row is not None and row["status"] != "open":
        store._db.execute(
            """UPDATE work_backlog
               SET kind = ?, target_specialist = ?, payload = ?,
                   priority = ?, created_by = 'conductor-invent',
                   origin = 'invented', value_case = ?,
                   status = 'open', updated_at = ?
               WHERE id = ?""",
            (cand["kind"], cand["target"], payload, priority,
             cand["value_case"], _now(), row["id"]))
        store._db.commit()
        return row["id"]
    return add_backlog(
        store, owner, cand["title"], cand["kind"],
        target_specialist=cand["target"],
        payload=payload,
        priority=priority,
        created_by="conductor-invent",
        origin="invented",
        value_case=cand["value_case"])


def _clean_reason_for(tag: str) -> str:
    reasons = {
        "stale-verification": "all receipted missions re-verified since "
                              "their receipts",
        "allocation-risk": "no allocation ≥80% consumed and no use-or-lose "
                           "allocation expiring within 7 days",
        "grade-gap": "every specialist with runs has a Mentor grade in "
                     "the last 14 days",
        "rotation-gap": "every active specialist has run at least once",
    }
    return reasons.get(tag, "pattern came back clean")


def invented_report(store: Store, owner: str, days: int = 7) -> dict:
    """Weekly-report fuel: how much invented work there was, what got
    assigned, what completed. Just the numbers — the report wording is
    someone else's job."""
    _ensure_schema(store)
    since = f"datetime('now', '-{int(days)} days')"
    inv = store._db.execute(
        f"SELECT COUNT(*) AS n FROM work_backlog WHERE owner = ? "
        f"AND origin = 'invented' AND created_at >= {since}",
        (owner,)).fetchone()["n"]
    asg = store._db.execute(
        f"SELECT COUNT(*) AS n FROM assignments a "
        f"JOIN work_backlog w ON w.id = a.backlog_id "
        f"WHERE a.owner = ? AND w.origin = 'invented' "
        f"AND a.assigned_at >= {since}", (owner,)).fetchone()["n"]
    done = store._db.execute(
        f"SELECT COUNT(*) AS n FROM assignments a "
        f"JOIN work_backlog w ON w.id = a.backlog_id "
        f"WHERE a.owner = ? AND w.origin = 'invented' "
        f"AND w.status = 'done' AND a.assigned_at >= {since}",
        (owner,)).fetchone()["n"]
    return {"days": int(days), "invented": inv, "assigned": asg,
            "completed": done}
