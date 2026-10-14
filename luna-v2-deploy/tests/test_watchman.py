"""Tests for the Watchman specialist (luna_v2/watchman.py).

Watchman is read-only over Luna's state: it writes only its own
report rows (plus one best-effort Guardian suggestion on
degraded/critical results) and makes zero provider calls.
"""

from datetime import datetime, timezone

import pytest

from luna_v2 import watchman as W
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _seed_healthy(store):
    """A closed mission with a receipt, reconciled usage, and some
    successful specialist runs. Guardian is NOT initialized here."""
    mid = store.create_mission(OWNER, "Done work", "receipt-worthy")
    sid = store.add_step(mid, OWNER, "do the thing", "routine", seq=1)
    store.update_step(sid, status="done", result="ok", evidence="proof")
    store.update_mission(mid, status="closed")
    store.add_receipt(mid, OWNER, "all done", '{"steps": 1}')
    used_at = _now()
    store.add_usage(OWNER, "groq", "tokens", 100.0, used_at, mission_id=mid)
    store.add_ledger_entry(OWNER, "groq", "tokens", 100.0, 0.0, 0.0,
                           "run 1", mission_id=mid)
    store._db.execute(
        "CREATE TABLE IF NOT EXISTS specialist_runs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, specialist TEXT NOT NULL, "
        "owner TEXT NOT NULL, mission_id INTEGER, step_id INTEGER, "
        "question TEXT NOT NULL DEFAULT '', sources_json TEXT NOT NULL "
        "DEFAULT '[]', status TEXT NOT NULL DEFAULT 'started', "
        "result TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL)")
    for _ in range(3):
        store._db.execute(
            "INSERT INTO specialist_runs (specialist, owner, mission_id, "
            "step_id, question, status, created_at) "
            "VALUES ('scout', ?, ?, NULL, 'q', 'done', ?)",
            (OWNER, mid, _now()))
    store._db.commit()
    return mid


def _statuses(result):
    return {c["check"]: c["status"] for c in result["checks"]}


def test_healthy_db_reports_healthy_and_records_report(store):
    _seed_healthy(store)
    result = W.health_check(store, OWNER)
    assert result["status"] == "healthy"
    assert _statuses(result) == {
        "db_integrity": "pass",
        "ledger_reconciliation": "pass",
        "receipt_coverage": "pass",
        "specialist_failure_share": "pass",
        "guardian_inbox": "info",   # guardian not initialized -> info
    }
    # the report row is recorded with the same status
    row = W.get_report(store, result["report_id"])
    assert row is not None
    assert row["status"] == "healthy"
    assert row["owner"] == OWNER
    # a healthy check files no Guardian suggestion
    assert store._db.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' "
        "AND name='guardian_suggestions'").fetchone()["n"] == 0


def test_ledger_drift_is_critical_with_exact_figures(store):
    _seed_healthy(store)
    # an unmatched ledger row: 100 used, 105 in the ledger
    store.add_ledger_entry(OWNER, "groq", "tokens", 5.0, 0.0, 0.0,
                           "rogue entry")
    result = W.health_check(store, OWNER)
    assert result["status"] == "critical"
    recon = next(c for c in result["checks"]
                 if c["check"] == "ledger_reconciliation")
    assert recon["status"] == "critical"
    assert "groq/tokens" in recon["detail"]
    assert "usage 100" in recon["detail"]
    assert "ledger 105" in recon["detail"]
    # degraded/critical results file exactly ONE guardian suggestion
    n_open = store._db.execute(
        "SELECT COUNT(*) AS n FROM guardian_suggestions "
        "WHERE owner = ? AND status = 'open'", (OWNER,)).fetchone()["n"]
    assert n_open == 1
    # a rescan does not file a duplicate
    W.health_check(store, OWNER)
    n_open = store._db.execute(
        "SELECT COUNT(*) AS n FROM guardian_suggestions "
        "WHERE owner = ? AND status = 'open'", (OWNER,)).fetchone()["n"]
    assert n_open == 1


def test_closed_mission_without_receipt_is_degraded(store):
    mid = _seed_healthy(store)
    store._db.execute("DELETE FROM receipts WHERE mission_id = ?", (mid,))
    result = W.health_check(store, OWNER)
    assert result["status"] == "degraded"
    coverage = next(c for c in result["checks"]
                    if c["check"] == "receipt_coverage")
    assert coverage["status"] == "degraded"
    assert str(mid) in coverage["detail"]


def test_guardian_inbox_without_guardian_table_is_info(store):
    # fresh store: guardian_suggestions does not exist
    result = W.health_check(store, OWNER)
    inbox = next(c for c in result["checks"]
                 if c["check"] == "guardian_inbox")
    assert inbox["status"] == "info"
    assert "not initialized" in inbox["detail"]


def test_specialist_failure_share_flags_majority_failures(store):
    _seed_healthy(store)  # 3 done runs already
    for _ in range(4):  # 4 failed of 7 recent runs (57% > 50%)
        store._db.execute(
            "INSERT INTO specialist_runs (specialist, owner, mission_id, "
            "step_id, question, status, error, created_at) "
            "VALUES ('scout', ?, NULL, NULL, 'q', 'failed', 'boom', ?)",
            (OWNER, _now()))
    store._db.commit()
    result = W.health_check(store, OWNER)
    share = next(c for c in result["checks"]
                 if c["check"] == "specialist_failure_share")
    assert share["status"] == "degraded"
    assert "4 failed of 7" in share["detail"]
    assert result["status"] == "degraded"


def test_health_check_is_read_only_and_makes_no_provider_calls(store):
    """Nothing in Luna's own tables changes under a healthy scan, and
    watchman never touches the provider machinery."""
    _seed_healthy(store)
    before = {
        "missions": store._db.execute("SELECT COUNT(*) AS n FROM missions")
        .fetchone()["n"],
        "usage": store._db.execute("SELECT COUNT(*) AS n FROM broker_usage")
        .fetchone()["n"],
        "ledger": store._db.execute("SELECT COUNT(*) AS n FROM broker_ledger")
        .fetchone()["n"],
    }
    assert "dispatch" not in open(W.__file__).read().replace(
        "provider_dispatch", "")
    W.health_check(store, OWNER)
    assert store._db.execute("SELECT COUNT(*) AS n FROM missions").fetchone()[
        "n"] == before["missions"]
    assert store._db.execute(
        "SELECT COUNT(*) AS n FROM broker_usage").fetchone()["n"] == \
        before["usage"]
    assert store._db.execute(
        "SELECT COUNT(*) AS n FROM broker_ledger").fetchone()["n"] == \
        before["ledger"]
