"""Watchman: Luna's health watchman.

Jason's direction (2026-10-13): Luna grows a TEAM of specialists that
expand the AI agent ecosystem. Watchman watches Luna's own health with
read-only checks and reports drift or breakage instead of letting it
go quiet.

Design rules (deliberate):
- READ-ONLY over Luna's state. health_check SELECTs from the store's
  own tables (missions, steps, receipts, broker usage/ledger,
  specialist runs, guardian suggestions). Its only writes are its own
  report rows (watchman_reports) and, on degraded/critical results, a
  single Guardian suggestion. It never modifies missions, the broker,
  usage, receipts, or anything else, and it makes ZERO provider
  calls — a health check never spends free fuel.
- The Guardian filing is best-effort: it is wrapped so that any
  failure in Guardian can never break health_check.
- Checks degrade cleanly on tables that do not exist (fresh or older
  databases): a missing specialist_runs or guardian_suggestions table
  is reported as info, never a crash.

Stdlib only.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2.store import Store


class WatchmanError(M.LunaError):
    """Base error for the Watchman."""


HEALTHY = "healthy"
DEGRADED = "degraded"
CRITICAL = "critical"
_STATUSES = (HEALTHY, DEGRADED, CRITICAL)
# Per-check verdicts: pass/info are non-alarming.
_CHECK_ALARM = {"pass": 0, "info": 0, "degraded": 1, "critical": 2}
# Tiny tolerance for REAL sums (recorded amounts are identical floats,
# but never trip on dust).
_EPSILON = 1e-9

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchman_reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('healthy','degraded','critical')),
    checks_json TEXT NOT NULL DEFAULT '[]'
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(SCHEMA)
    store._db.commit()


def _table_exists(store: Store, name: str) -> bool:
    row = store._db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,)).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# The checks (each returns a {check, status, detail} dict; none writes,
# none calls a provider)
# ---------------------------------------------------------------------------
def _check_db_integrity(store: Store, owner: str) -> dict:
    """critical: PRAGMA integrity_check must return only 'ok' rows."""
    try:
        rows = store._db.execute("PRAGMA integrity_check").fetchall()
        bad = [r[0] for r in rows if r[0].lower() != "ok"]
    except sqlite3.Error as e:
        return {"check": "db_integrity", "status": "critical",
                "detail": f"PRAGMA integrity_check failed: {e}"}
    if bad:
        return {"check": "db_integrity", "status": "critical",
                "detail": f"integrity_check reported: {'; '.join(bad[:5])}"}
    return {"check": "db_integrity", "status": "pass",
            "detail": "PRAGMA integrity_check ok"}


def _check_ledger_reconciliation(store: Store, owner: str) -> dict:
    """critical: per provider+unit, SUM(broker_usage.amount) must equal
    SUM(broker_ledger.amount). Any drift means the resource ledger no
    longer reflects recorded usage."""
    usage = {}
    for r in store._db.execute(
            "SELECT provider, unit, COALESCE(SUM(amount), 0) AS total "
            "FROM broker_usage WHERE owner = ? GROUP BY provider, unit",
            (owner,)).fetchall():
        usage[(r["provider"], r["unit"])] = r["total"]
    ledger = {}
    for r in store._db.execute(
            "SELECT provider, unit, COALESCE(SUM(amount), 0) AS total "
            "FROM broker_ledger WHERE owner = ? GROUP BY provider, unit",
            (owner,)).fetchall():
        ledger[(r["provider"], r["unit"])] = r["total"]
    drifts = []
    for key in sorted(set(usage) | set(ledger)):
        u = usage.get(key, 0.0)
        l = ledger.get(key, 0.0)
        if abs(u - l) > _EPSILON:
            drifts.append(f"{key[0]}/{key[1]}: usage {u:g} vs ledger {l:g} "
                          f"(delta {l - u:g})")
    if drifts:
        return {"check": "ledger_reconciliation", "status": "critical",
                "detail": "drift: " + "; ".join(drifts)}
    return {"check": "ledger_reconciliation", "status": "pass",
            "detail": f"{len(usage)} provider/unit pair(s) reconcile "
                      "(usage totals match ledger totals)"}


def _check_receipt_coverage(store: Store, owner: str) -> dict:
    """degraded: every closed mission must have exactly one receipt."""
    rows = store._db.execute(
        "SELECT m.id AS mid, COUNT(r.id) AS n "
        "FROM missions m LEFT JOIN receipts r ON r.mission_id = m.id "
        "WHERE m.owner = ? AND m.status = 'closed' "
        "GROUP BY m.id", (owner,)).fetchall()
    missing = [str(r["mid"]) for r in rows if r["n"] == 0]
    extra = [str(r["mid"]) for r in rows if r["n"] > 1]
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"no receipt for mission(s) {', '.join(missing)}")
        if extra:
            parts.append(f"multiple receipts for mission(s) "
                         f"{', '.join(extra)}")
        return {"check": "receipt_coverage", "status": "degraded",
                "detail": "; ".join(parts)}
    return {"check": "receipt_coverage", "status": "pass",
            "detail": (f"all {len(rows)} closed mission(s) have exactly "
                       "one receipt") if rows else "no closed missions"}


def _check_specialist_failure_share(store: Store, owner: str) -> dict:
    """info/degraded: failure share over the last 20 specialist_runs.
    info when there are no runs; degraded only with >= 4 runs and a
    failure share above 50%."""
    if not _table_exists(store, "specialist_runs"):
        return {"check": "specialist_failure_share", "status": "info",
                "detail": "no specialist runs recorded yet "
                          "(specialist_runs table absent)"}
    rows = store._db.execute(
        "SELECT status FROM specialist_runs WHERE owner = ? "
        "ORDER BY id DESC LIMIT 20", (owner,)).fetchall()
    if not rows:
        return {"check": "specialist_failure_share", "status": "info",
                "detail": "no specialist runs recorded yet"}
    failed = sum(1 for r in rows if r["status"] == "failed")
    share = failed / len(rows)
    detail = f"{failed} failed of {len(rows)} recent runs ({share:.0%})"
    if len(rows) >= 4 and share > 0.5:
        return {"check": "specialist_failure_share", "status": "degraded",
                "detail": detail}
    return {"check": "specialist_failure_share", "status": "pass",
            "detail": detail}


def _check_guardian_inbox(store: Store, owner: str) -> dict:
    """Report open Guardian suggestions by severity. A missing
    guardian_suggestions table is info ('guardian not initialized'),
    never a crash. Open critical/warning suggestions escalate the
    check so they do not go quiet."""
    if not _table_exists(store, "guardian_suggestions"):
        return {"check": "guardian_inbox", "status": "info",
                "detail": "guardian not initialized on this database "
                          "(no guardian_suggestions table)"}
    rows = store._db.execute(
        "SELECT severity, COUNT(*) AS n FROM guardian_suggestions "
        "WHERE owner = ? AND status IN ('open', 'acknowledged') "
        "GROUP BY severity", (owner,)).fetchall()
    counts = {r["severity"]: r["n"] for r in rows}
    total = sum(counts.values())
    detail = ("open suggestions: "
              + ", ".join(f"{counts.get(s, 0)} {s}"
                          for s in ("critical", "warning", "info")))
    if counts.get("critical"):
        return {"check": "guardian_inbox", "status": "critical",
                "detail": detail}
    if counts.get("warning"):
        return {"check": "guardian_inbox", "status": "degraded",
                "detail": detail}
    if total:
        return {"check": "guardian_inbox", "status": "info", "detail": detail}
    return {"check": "guardian_inbox", "status": "info",
            "detail": "no open suggestions"}


_CHECKS = (
    _check_db_integrity,
    _check_ledger_reconciliation,
    _check_receipt_coverage,
    _check_specialist_failure_share,
    _check_guardian_inbox,
)


# ---------------------------------------------------------------------------
# Reporting and the optional Guardian filing
# ---------------------------------------------------------------------------
def _overall(checks: list[dict]) -> str:
    level = max(_CHECK_ALARM[c["status"]] for c in checks)
    return {0: HEALTHY, 1: DEGRADED, 2: CRITICAL}[level]


def get_report(store: Store, report_id: int) -> sqlite3.Row | None:
    """Read one recorded health report."""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM watchman_reports WHERE id = ?", (report_id,)).fetchone()


def _maybe_file_guardian(store: Store, owner: str, status: str,
                         checks: list[dict]) -> None:
    """On degraded/critical results, file ONE Guardian suggestion about
    the watchman finding. Best-effort: any Guardian failure is
    swallowed so it can never break health_check."""
    if status == HEALTHY:
        return
    try:
        failing = [c for c in checks
                   if c["status"] in (DEGRADED, CRITICAL)]
        G.file_suggestion(
            store, owner, "watchman_health", "watchman health report",
            "critical" if status == CRITICAL else "warning",
            f"Watchman health check: {len(failing)} check(s) not healthy "
            f"(overall {status})",
            "; ".join(f"{c['check']}: {c['detail']}" for c in failing),
            "Rowan: investigate the failing checks above — each is "
            "read-only evidence from Luna's own database.")
    except Exception:
        pass


def health_check(store: Store, owner: str = "jason") -> dict:
    """Run every health check, record the report, and return it.

    Returns {report_id, owner, status, checks, created_at}. Makes zero
    provider calls and writes only to watchman_reports (plus one
    Guardian suggestion on degraded/critical results, best-effort).
    """
    _ensure_schema(store)
    checks = [check(store, owner) for check in _CHECKS]
    status = _overall(checks)
    created = _now()
    cur = store._db.execute(
        "INSERT INTO watchman_reports (owner, created_at, status, "
        "checks_json) VALUES (?, ?, ?, ?)",
        (owner, created, status, json.dumps(checks)))
    store._db.commit()
    _maybe_file_guardian(store, owner, status, checks)
    return {"report_id": cur.lastrowid, "owner": owner, "status": status,
            "checks": checks, "created_at": created}
