"""Tests for the Verifier specialist (luna_v2/verifier.py)."""

import json

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import missions as M
from luna_v2 import verifier as V

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "verifier.db"))
    yield s
    s.close()


def _clean_closed(store, owner=OWNER):
    """A fully consistent closed mission: steps with evidence, a receipt,
    and mission-attributed usage + ledger rows via the broker's real API."""
    B.seed_providers(store, owner)
    m = M.create_mission(store, owner, "Clean job", outcome="all good")
    s1 = M.add_step(store, owner, m.id, "gather data", M.ROUTINE)
    s2 = M.add_step(store, owner, m.id, "write summary", M.ROUTINE)
    M.complete_step(store, s1.id, "data ok", "source: http://example.com/a")
    M.complete_step(store, s2.id, "summary ok", "summary written")
    B.record_usage(store, owner, "groq", "requests", 1.0, mission_id=m.id,
                   note="check")
    B.record_usage(store, owner, "groq", "tokens", 100.0, mission_id=m.id,
                   note="check")
    M.close_mission(store, m.id)
    return m


def _failing_check(result, name):
    return next(c for c in result.checks if c["check"] == name)


def test_clean_mission_verifies_pass(store):
    m = _clean_closed(store)
    result = V.verify_mission(store, m.id, fetcher=lambda url: "ok")
    assert result.verdict == "pass"
    assert all(c["status"] in ("pass", "info") for c in result.checks)
    assert _failing_check(result, "evidence_present")["status"] == "pass"
    assert _failing_check(result, "receipt_consistency")["status"] == "pass"
    assert _failing_check(result, "usage_reconciliation")["status"] == "pass"
    # the run itself was recorded
    rows = V.list_runs(store, m.id)
    assert len(rows) == 1 and rows[0]["verdict"] == "pass"


def test_doctored_receipt_fails_receipt_consistency(store):
    m = _clean_closed(store)
    store._db.execute(
        "UPDATE receipts SET evidence_json = ? WHERE mission_id = ?",
        (json.dumps({"evidence": []}), m.id))
    store._db.commit()
    result = V.verify_mission(store, m.id)
    assert result.verdict == "fail"
    check = _failing_check(result, "receipt_consistency")
    assert check["status"] == "fail"
    assert "differs" in check["detail"] or "missing" in check["detail"]


def test_done_step_without_evidence_fails(store):
    m = _clean_closed(store)
    store._db.execute(
        "INSERT INTO steps (mission_id, owner, seq, description, kind, "
        "status, result, evidence) VALUES (?, ?, ?, ?, ?, 'done', 'x', '')",
        (m.id, OWNER, 99, "sneaked in", "routine"))
    store._db.commit()
    result = V.verify_mission(store, m.id)
    assert result.verdict == "fail"
    check = _failing_check(result, "evidence_present")
    assert check["status"] == "fail"
    assert "no evidence" in check["detail"]


def test_extra_ledger_row_fails_usage_reconciliation(store):
    m = _clean_closed(store)
    store.add_ledger_entry(OWNER, "groq", "tokens", 50.0, 0.0, 0.0,
                           "planted", mission_id=m.id)
    result = V.verify_mission(store, m.id)
    assert result.verdict == "fail"
    check = _failing_check(result, "usage_reconciliation")
    assert check["status"] == "fail"


def test_missing_mission_raises_and_records_nothing(store):
    with pytest.raises(M.NotFound):
        V.verify_mission(store, 4242)
    assert V.list_runs(store) == []


def test_unreachable_citation_is_reported_not_failed(store):
    m = _clean_closed(store)

    def fetcher(url):
        if "example.com" in url:
            raise RuntimeError("connection refused")
        return "ok"

    result = V.verify_mission(store, m.id, fetcher=fetcher)
    assert result.verdict == "pass"  # reported, never a verdict fail in v1
    check = _failing_check(result, "citation_reachability")
    assert check["status"] == "info"
    assert "unreachable" in check["detail"]


def test_open_mission_receipt_check_is_info(store):
    B.seed_providers(store, OWNER)
    m = M.create_mission(store, OWNER, "Still going")
    M.add_step(store, OWNER, m.id, "first", M.ROUTINE)
    result = V.verify_mission(store, m.id)
    assert result.verdict == "pass"
    assert _failing_check(result, "receipt_consistency")["status"] == "info"


def test_mission_without_usage_still_reconciles(store):
    B.seed_providers(store, OWNER)
    m = M.create_mission(store, OWNER, "No fuel burned")
    s1 = M.add_step(store, OWNER, m.id, "think", M.ROUTINE)
    M.complete_step(store, s1.id, "thought", "my head")
    M.close_mission(store, m.id)
    result = V.verify_mission(store, m.id)
    assert result.verdict == "pass"
    assert _failing_check(result, "usage_reconciliation")["status"] == "pass"
