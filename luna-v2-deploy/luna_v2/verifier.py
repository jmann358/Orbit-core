"""Luna's Evidence Verifier specialist: an independent second look before a
receipt is trusted.

This closes the loop on the project's #1 hurdle (unreliable verification).
After a mission closes, Verifier re-checks the mission's stored record:
that every completed step carries evidence, that the receipt faithfully
captures that evidence, and that the mission's broker usage and ledger
entries reconcile. It optionally checks that URLs cited in evidence are
reachable. It produces a structured verdict ('pass' or 'fail') plus a
per-check breakdown.

Verifier is READ-ONLY over mission and broker state: it never writes to
missions, steps, receipts, or the broker. Its only write is its own
verification_runs table (owned by this module, CREATE TABLE IF NOT
EXISTS; store.py is never touched).

Deterministic apart from the optional fetcher, and ZERO provider calls in
v1 — the profile's dispatch budget stays unspent, deliberately. A
re-fetch-only fetch is the one network touch, and only when the caller
supplies a fetcher.

Stdlib only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from luna_v2 import missions as M
from luna_v2.store import Store


class VerifierError(M.LunaError):
    """Base error for the verifier specialist."""


URL_RE = re.compile(r"https?://[^\s<>\"']+")


# ---------------------------------------------------------------------------
# Run bookkeeping (table owned by this module; store.py untouched)
# ---------------------------------------------------------------------------
VERIFICATION_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS verification_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    mission_id  INTEGER NOT NULL,
    verdict     TEXT NOT NULL CHECK (verdict IN ('pass', 'fail')),
    checks_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(VERIFICATION_RUNS_SCHEMA)
    store._db.commit()


@dataclass
class VerificationResult:
    run_id: int
    verdict: str  # 'pass' or 'fail'
    # each check: {"check": name, "status": 'pass'|'fail'|'info', "detail": str}
    checks: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
def _check_evidence_present(steps: list) -> dict:
    done = [s for s in steps if s["status"] == "done"]
    bad = [s["id"] for s in done if not s["evidence"].strip()]
    if bad:
        return {"check": "evidence_present", "status": "fail",
                "detail": f"{len(bad)} done step(s) carry no evidence: "
                          f"{', '.join(map(str, bad))}"}
    return {"check": "evidence_present", "status": "pass",
            "detail": f"all {len(done)} done step(s) carry evidence"}


def _receipt_evidence_map(receipt_row) -> dict | None:
    """seq -> evidence recorded on the receipt, or None if unreadable."""
    try:
        payload = json.loads(receipt_row["evidence_json"])
        entries = payload["evidence"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return {e["seq"]: e.get("evidence", "") for e in entries
            if isinstance(e, dict) and "seq" in e}


def _check_receipt_consistency(mission: dict, steps: list,
                               receipt_row) -> dict:
    if mission["status"] != "closed":
        return {"check": "receipt_consistency", "status": "info",
                "detail": "mission is open; nothing to verify yet"}
    if receipt_row is None:
        return {"check": "receipt_consistency", "status": "fail",
                "detail": "mission is closed but has no receipt"}
    recorded = _receipt_evidence_map(receipt_row)
    if recorded is None:
        return {"check": "receipt_consistency", "status": "fail",
                "detail": "receipt evidence_json is not a readable "
                          "evidence payload"}
    mismatched = []
    missing = []
    for s in steps:
        seq = s["seq"]
        if seq not in recorded:
            missing.append(seq)
        elif recorded[seq] != s["evidence"]:
            mismatched.append(seq)
    if missing or mismatched:
        parts = []
        if missing:
            parts.append(f"steps missing from receipt: "
                         f"{', '.join(map(str, missing))}")
        if mismatched:
            parts.append(f"steps whose evidence differs from the receipt: "
                         f"{', '.join(map(str, mismatched))}")
        return {"check": "receipt_consistency", "status": "fail",
                "detail": "; ".join(parts)}
    return {"check": "receipt_consistency", "status": "pass",
            "detail": f"receipt captures the evidence of all "
                      f"{len(steps)} step(s) exactly"}


def _sums_by_provider_unit(store: Store, table: str,
                           mission_id: int) -> dict:
    rows = store._db.execute(
        f"SELECT provider, unit, COUNT(*) AS n, SUM(amount) AS total "
        f"FROM {table} WHERE mission_id = ? "
        f"GROUP BY provider, unit", (mission_id,)).fetchall()
    return {(r["provider"], r["unit"]): (r["n"], r["total"]) for r in rows}


def _check_usage_reconciliation(store: Store, mission_id: int) -> dict:
    usage = _sums_by_provider_unit(store, "broker_usage", mission_id)
    ledger = _sums_by_provider_unit(store, "broker_ledger", mission_id)
    if usage.keys() != ledger.keys():
        only_usage = sorted(set(usage) - set(ledger))
        only_ledger = sorted(set(ledger) - set(usage))
        parts = []
        if only_usage:
            parts.append(f"usage without ledger: "
                         f"{', '.join(f'{p}/{u}' for p, u in only_usage)}")
        if only_ledger:
            parts.append(f"ledger without usage: "
                         f"{', '.join(f'{p}/{u}' for p, u in only_ledger)}")
        return {"check": "usage_reconciliation", "status": "fail",
                "detail": "; ".join(parts)}
    mismatched = []
    for key in usage:
        n_u, total_u = usage[key]
        n_l, total_l = ledger[key]
        if n_u != n_l or abs((total_u or 0.0) - (total_l or 0.0)) > 1e-9:
            mismatched.append(
                f"{key[0]}/{key[1]}: {n_u} usage row(s) vs {n_l} ledger "
                f"row(s), {total_u:g} vs {total_l:g}")
    if mismatched:
        return {"check": "usage_reconciliation", "status": "fail",
                "detail": "; ".join(mismatched)}
    n_units = len(usage)
    return {"check": "usage_reconciliation", "status": "pass",
            "detail": f"usage and ledger reconcile across {n_units} "
                      f"provider/unit pair(s) for this mission"}


def _check_citation_reachability(steps: list, fetcher) -> dict:
    urls = []
    seen = set()
    for s in steps:
        if s["status"] != "done":
            continue
        for url in URL_RE.findall(s["evidence"] or ""):
            if url not in seen:
                seen.add(url)
                urls.append(url)
    if not urls:
        return {"check": "citation_reachability", "status": "info",
                "detail": "no citations found in step evidence"}
    if fetcher is None:
        return {"check": "citation_reachability", "status": "info",
                "detail": f"{len(urls)} citation(s) present; not fetched "
                          f"(no fetcher supplied)"}
    reachable, unreachable = [], []
    for url in urls:
        try:
            fetcher(url)
            reachable.append(url)
        except Exception as e:  # reported, never a verdict fail in v1
            unreachable.append(f"{url} ({e})")
    detail = f"{len(reachable)}/{len(urls)} citation(s) reachable"
    if unreachable:
        detail += f"; unreachable: {'; '.join(unreachable)}"
    return {"check": "citation_reachability", "status": "info",
            "detail": detail}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def verify_mission(store: Store, mission_id: int, *,
                   owner: str = "jason", fetcher=None) -> VerificationResult:
    """Run all verifier checks against a mission. Raises M.NotFound for a
    missing mission (nothing is recorded in that case). Otherwise records
    the run and returns a VerificationResult with verdict 'pass' or 'fail'.
    Verdict is 'fail' iff any check fails."""
    _ensure_schema(store)
    mission = store.get_mission(mission_id)
    if mission is None:
        raise M.NotFound(f"mission {mission_id} not found")
    steps = store.list_steps(mission_id)

    checks = [
        _check_evidence_present(steps),
        _check_receipt_consistency(mission, steps,
                                   store.get_receipt(mission_id)),
        _check_usage_reconciliation(store, mission_id),
        _check_citation_reachability(steps, fetcher),
    ]
    verdict = "fail" if any(c["status"] == "fail" for c in checks) else "pass"

    cur = store._db.execute(
        "INSERT INTO verification_runs "
        "(owner, mission_id, verdict, checks_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (owner, mission_id, verdict, json.dumps(checks), _now()))
    store._db.commit()
    return VerificationResult(run_id=cur.lastrowid, verdict=verdict,
                              checks=checks)


def list_runs(store: Store, mission_id: int | None = None) -> list:
    """All verification runs (optionally for one mission), newest last."""
    _ensure_schema(store)
    if mission_id is None:
        return store._db.execute(
            "SELECT * FROM verification_runs ORDER BY id").fetchall()
    return store._db.execute(
        "SELECT * FROM verification_runs WHERE mission_id = ? ORDER BY id",
        (mission_id,)).fetchall()
