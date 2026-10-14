"""Quartermaster — Luna's resource steward.

Manages the free-allocation inventory: burn rates, exhaustion warnings,
use-it-or-lose-it flags, all computed from the broker's real numbers.

Deliberate rules:
- Quartermaster READS the broker and never spends. No provider calls, no
  usage recording, no ledger writes from this module — flagging is
  observation, not consumption.
- Quota math is never reimplemented here: allocation figures come from
  broker.list_allocations(), and the route pick comes from broker.route()
  (which is read-only). The only logic Quartermaster owns is flagging,
  kept in a pure function so it is testable without a database.
- Flag semantics (boundary values are deliberate):
  - LOW: remaining < 20% of the allowance. Exactly 20% is NOT low.
  - EXHAUSTED: remaining == 0. Takes precedence over LOW.
  - USE_OR_LOSE: remaining > 50% AND the period resets within 24 hours.
    Exactly 50% is NOT use-or-lose. A healthy allocation you simply will
    not burn through before reset is the flag's whole point.
- Only routable production allocations (broker's own classification:
  status active, production allowed, known allowance) appear in the
  report. Retired, evaluation-only, and unknown-quota providers are
  the broker's job to inventory, not Quartermaster's to flag.

Stdlib only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from luna_v2 import broker as B
from luna_v2.store import Store

# Seconds in the "use it or lose it" window.
USE_OR_LOSE_WINDOW_S = 24 * 3600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Run bookkeeping (table owned by this module; store.py is never touched)
# ---------------------------------------------------------------------------
QM_REPORTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS qm_reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    report_json TEXT NOT NULL DEFAULT '{}'
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.execute(QM_REPORTS_SCHEMA)
    store._db.commit()


# ---------------------------------------------------------------------------
# Flagging — pure function over allocation figures. No database needed.
# ---------------------------------------------------------------------------
def flags_for_allocation(total: float, remaining: float,
                         resets_in_seconds: float) -> list[str]:
    """Flag an allocation. Boundary values are exact per the module rules:

    - remaining == 0            -> ["EXHAUSTED"] (never ["LOW"])
    - 0 < remaining < 20%       -> ["LOW"]
    - remaining == exactly 20%  -> []  (boundary is not low)
    - remaining > 50% AND resets within 24h -> ["USE_OR_LOSE"]
    - remaining == exactly 50%  -> []  (boundary is not use-or-lose)
    - resets at exactly 24h     -> counts as "within 24 hours"
    """
    if total <= 0:
        return ["EXHAUSTED"] if remaining <= 0 else []
    share = remaining / total
    if remaining <= 0:
        return ["EXHAUSTED"]
    if share > 0.5 and resets_in_seconds <= USE_OR_LOSE_WINDOW_S:
        return ["USE_OR_LOSE"]
    if share < 0.20:
        return ["LOW"]
    return []


def _fmt_resets_in(seconds: float) -> str:
    secs = max(int(seconds), 0)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def _num(x: float) -> str:
    """Compact number: 4636, 200,000, 0.5 — readable in a text report."""
    if x is None:
        return "?"
    if float(x).is_integer():
        return f"{int(x):,}"
    return f"{x:g}"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
REFERENCE_NEEDS = {"requests": 1.0, "tokens": 500.0}


def report(store: Store, owner: str = "jason",
           now: datetime | None = None) -> dict:
    """Build the Quartermaster report from the broker's real allocation
    figures. Records the report row. Makes zero provider calls and records
    zero usage — read-only observation."""
    _ensure_schema(store)
    now = now or datetime.now(timezone.utc)

    allocations = []
    for a in B.list_allocations(store, owner, now):
        if not a.routable:
            continue
        remaining = a.remaining  # never None here: routable implies allowance known
        resets_s = a.resets_in.total_seconds()
        allocations.append({
            "provider": a.provider,
            "unit": a.unit,
            "used": a.used,
            "total": a.allowance,
            "remaining": remaining,
            "pct_used": (a.used / a.allowance * 100) if a.allowance else 0.0,
            "period": a.period,
            "resets_in_seconds": resets_s,
            "resets_in": _fmt_resets_in(resets_s),
            "flags": flags_for_allocation(a.allowance, remaining, resets_s),
        })

    totals: dict[str, dict] = {}
    for a in allocations:
        t = totals.setdefault(a["unit"],
                              {"used": 0.0, "total": 0.0, "remaining": 0.0})
        t["used"] += a["used"]
        t["total"] += a["total"]
        t["remaining"] += a["remaining"]

    # The route pick is computed, never executed: broker.route() is
    # read-only — it routes on paper. If nothing is eligible, say so.
    try:
        choice = B.route(store, owner, dict(REFERENCE_NEEDS), now)
        route_pick = {
            "eligible": True,
            "provider": choice.provider,
            "needs": choice.needs,
            "remaining_after": choice.remaining_after,
            "resets_in": _fmt_resets_in(choice.resets_in.total_seconds()),
            "note": choice.note,
        }
    except B.NoEligibleProvider as e:
        route_pick = {"eligible": False, "reason": str(e)}

    result = {
        "owner": owner,
        "created_at": _now(),
        "allocations": allocations,
        "totals": totals,
        "route_pick": route_pick,
    }
    cur = store._db.execute(
        "INSERT INTO qm_reports (owner, created_at, report_json) "
        "VALUES (?, ?, ?)",
        (owner, result["created_at"], json.dumps(result)))
    store._db.commit()
    result["report_id"] = cur.lastrowid
    return result


def get_report(store: Store, report_id: int) -> dict | None:
    """Re-read a recorded report."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT report_json FROM qm_reports WHERE id = ?",
        (report_id,)).fetchone()
    return json.loads(row["report_json"]) if row else None


def render_text(rep: dict) -> str:
    """Compact plain-text rendering of a report()."""
    lines = []
    for a in rep["allocations"]:
        flag_txt = (" [" + ", ".join(a["flags"]) + "]"
                    if a["flags"] else "")
        lines.append(
            f"{a['provider']}/{a['unit']}: {_num(a['used'])}/{_num(a['total'])} "
            f"used ({a['pct_used']:.1f}%), {_num(a['remaining'])} left, "
            f"resets in {a['resets_in']}{flag_txt}")
    if not lines:
        lines.append("(no routable production allocations)")
    tot = rep["totals"]
    if tot:
        lines.append("totals: " + "; ".join(
            f"{unit}: {_num(t['used'])}/{_num(t['total'])} used"
            for unit, t in sorted(tot.items())))
    rp = rep["route_pick"]
    if rp.get("eligible"):
        lines.append(
            f"route pick for a small job (1 request / 500 tokens): "
            f"{rp['provider']} — {rp['note']}")
    else:
        lines.append(f"route pick: no eligible provider — {rp.get('reason', '')}")
    return "\n".join(lines)
