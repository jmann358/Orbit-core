"""Herald — Luna's briefer.

Jason's reporting format is law here, composed deterministically from
real records: SHORT version first, a FLOW (the sequence, in plain
marks), NOTES flagging exactly what was left out, and a STAMP proving
the summary matches the source. The stamp is never claimed — it is
always run, and every compose names the real check that backs it:

- mission briefings: backed by verifier.verify_mission (evidence
  present, receipt consistency, usage reconciliation, citation
  reachability — all four, on the real records).
- storm briefings: backed by watchman.health_check's verdict.
- rewards briefings: backed by rewards.cross_check over the real
  ledger.

Zero provider calls. The `briefings` table is owned by this module
(CREATE TABLE IF NOT EXISTS); store.py is never touched.

Stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import missions as M
from luna_v2 import rewards as RW
from luna_v2 import stormwatch as SW
from luna_v2 import verifier as V
from luna_v2 import watchman as WM
from luna_v2.store import Store

BRIEFING_KINDS = ("mission", "storm", "rewards")

# Plain status marks for the flow line. The mission engine's step
# statuses are open/done/skipped; "failed" is kept in the table so a
# future failure status renders honestly instead of vanishing.
STEP_MARKS = {"done": "\u2713", "failed": "\u2717"}
PENDING_MARK = "\u00b7"

BRIEFINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS briefings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    kind       TEXT NOT NULL
               CHECK (kind IN ('mission','storm','rewards')),
    ref        TEXT NOT NULL DEFAULT '',
    short_text TEXT NOT NULL,
    flow_text  TEXT NOT NULL,
    notes      TEXT NOT NULL,
    stamp      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(BRIEFINGS_SCHEMA)
    store._db.commit()


def _asdict(row: Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _save(store: Store, owner: str, kind: str, ref: str,
          short_text: str, flow_text: str, notes: str,
          stamp: str) -> dict:
    _ensure_schema(store)
    cur = store._db.execute(
        "INSERT INTO briefings (owner, kind, ref, short_text, flow_text,"
        " notes, stamp, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (owner, kind, ref, short_text, flow_text, notes, stamp, _now()))
    store._db.commit()
    return _asdict(store._db.execute(
        "SELECT * FROM briefings WHERE id = ?",
        (cur.lastrowid,)).fetchone())


def _mark(status: str) -> str:
    return STEP_MARKS.get(status, PENDING_MARK)


def _resource_line(store: Store, owner: str, mission_id: int) -> str:
    rows = store._db.execute(
        "SELECT provider, unit, SUM(amount) AS total FROM broker_usage "
        "WHERE owner = ? AND mission_id = ? GROUP BY provider, unit",
        (owner, mission_id)).fetchall()
    if not rows:
        return "no provider usage recorded"
    return "; ".join(
        f"{r['provider']}: {r['total']:g} {r['unit']}" for r in rows)


# Verifier check statuses: "pass" and "fail" decide the verdict;
# "info" (citation_reachability) never fails it — so the stamp must
# not render an info check as a failure.
_CHECK_MARKS = {"pass": "✓", "fail": "✗", "info": "ⓘ"}


def _stamp_for_verdict(verdict: str, checks: list) -> str:
    bits = [f"{c['check']} {_CHECK_MARKS.get(c['status'], '?')}"
            for c in checks]
    if verdict == "fail":
        bad = [c["check"] for c in checks if c["status"] == "fail"]
        return f"CHECK FAILED: {', '.join(bad)} ({'; '.join(bits)})"
    return f"VERIFIED: pass ({'; '.join(bits)})"


# ---------------------------------------------------------------------------
# Mission briefings
# ---------------------------------------------------------------------------
def compose_mission_briefing(store: Store, owner: str,
                             mission_id: int) -> dict:
    """Compose Jason's four-part briefing for a mission, from real
    records, and save it. The stamp is backed by a real
    verifier.verify_mission run against this mission."""
    mission = store.get_mission(mission_id)
    if mission is None:
        raise M.NotFound(f"mission {mission_id} not found")
    steps = store.list_steps(mission_id)
    receipt = store.get_receipt(mission_id)

    done = [s for s in steps if s["status"] == M.STEP_DONE]
    skipped = [s for s in steps if s["status"] == M.STEP_SKIPPED]
    evidenced = [s for s in steps if s["evidence"]]
    outcome = mission["outcome"] or "not closed yet"

    short_lines = [
        f"Mission: {mission['title']}",
        f"Status: {mission['status']} · Outcome: {outcome}",
        f"Receipt: {receipt['id'] if receipt is not None else 'no receipt'}",
        (f"Steps: {len(done)} done of {len(steps)} "
         f"({len(skipped)} skipped)"),
        f"Resources: {_resource_line(store, owner, mission_id)}",
    ]
    flow = " \u2192 ".join(
        f"{_mark(s['status'])} {s['description']}" for s in steps)
    notes = (f"Full record holds {len(evidenced)} evidence entries "
             f"and {len(steps)} step details — ask for the long version.")

    result = V.verify_mission(store, mission_id, owner=owner)
    stamp = _stamp_for_verdict(result.verdict, result.checks)

    return _save(store, owner, "mission", str(mission_id),
                 "\n".join(short_lines), flow, notes, stamp)


# ---------------------------------------------------------------------------
# Storm briefings
# ---------------------------------------------------------------------------
def _watch_days(store: Store, owner: str) -> list[dict]:
    try:
        rows = store._db.execute(
            "SELECT day, summary, status FROM storm_watch_days "
            "WHERE owner = ? ORDER BY day", (owner,)).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def compose_storm_briefing(store: Store, owner: str) -> dict:
    """Compose Jason's four-part storm briefing. The stamp is the
    watchman.health_check verdict run against the real state."""
    st = SW.status(store, owner)
    days = _watch_days(store, owner)
    snaps = st["snapshots"]

    short_lines = [
        f"Storm watch: mode {st['mode']}",
        ("Home point: set" if st["home_set"]
         else "Home point: not set"),
        (f"Watching: {len(days)} day(s)"
         + (f" ({', '.join(d['day'] for d in days)})" if days else "")),
        ("Latest snapshot: " + (snaps[0]["created_at"] if snaps
                                 else "none")),
    ]
    flow = " \u2192 ".join(
        f"{d['day']} ({d['status']})" for d in days) or "no flagged days"
    if snaps:
        flow += f" \u2192 newest snapshot {snaps[0]['created_at']}"
    notes = (f"Full record holds {len(st['recent_events'])} recent "
             f"events and {len(snaps)} snapshots — ask for the long version.")

    report = WM.health_check(store, owner)
    if report["status"] == "healthy":
        stamp = f"WATCHMAN: healthy (report {report['report_id']})"
    else:
        bad = [c["check"] for c in report["checks"]
               if c["status"] != "healthy"]
        stamp = (f"CHECK FAILED: watchman {report['status']} "
                 f"({', '.join(bad)})")

    return _save(store, owner, "storm", "", "\n".join(short_lines),
                 flow, notes, stamp)


# ---------------------------------------------------------------------------
# Rewards briefings
# ---------------------------------------------------------------------------
def compose_rewards_briefing(store: Store, owner: str) -> dict:
    """Compose Jason's four-part rewards briefing. The stamp is the
    rewards.cross_check outcome over the real ledger."""
    rows = RW.list_rewards(store, owner)
    by_tier: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for r in rows:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    tickets = [t for t in RW.list_requests(store, owner, "ticket")
               if t["status"] == "pending"]
    tier_line = ", ".join(
        f"{t} {by_tier.get(t, 0)}" for t in RW.TIERS)

    short_lines = [
        f"Rewards ledger: {len(rows)} grant(s) "
        f"({by_status.get('active', 0)} active, "
        f"{by_status.get('expired', 0)} expired)",
        f"By tier: {tier_line}",
        ("Golden tickets pending: " + str(len(tickets))
         + (f" ({', '.join(t['specialist'] for t in tickets)})"
            if tickets else "")),
    ]
    flow = " \u2192 ".join(
        f"{t} \u00d7{by_tier.get(t, 0)}" for t in RW.TIERS
        if by_tier.get(t, 0)) or "no grants yet"
    notes = (f"Full record holds {len(rows)} grant rows and "
             f"{len(RW.list_requests(store, owner, 'ticket'))} ticket "
             f"requests — ask for the long version.")

    findings = RW.cross_check(store, owner)
    if not findings:
        stamp = f"CROSS-CHECK: clean ({len(rows)} ledger rows)"
    else:
        first = findings[0].get("reason", str(findings[0]))
        stamp = (f"CHECK FAILED: {len(findings)} finding(s) — "
                 f"{first}")

    return _save(store, owner, "rewards", "", "\n".join(short_lines),
                 flow, notes, stamp)


def list_briefings(store: Store, owner: str,
                   kind: str | None = None) -> list[dict]:
    _ensure_schema(store)
    if kind is not None and kind not in BRIEFING_KINDS:
        raise M.LunaError(
            f"kind must be one of {', '.join(BRIEFING_KINDS)}, "
            f"got {kind!r}")
    q = ("SELECT * FROM briefings WHERE owner = ? ORDER BY id")
    rows = store._db.execute(q, (owner,)).fetchall()
    out = [_asdict(r) for r in rows]
    return [r for r in out if kind is None or r["kind"] == kind]
