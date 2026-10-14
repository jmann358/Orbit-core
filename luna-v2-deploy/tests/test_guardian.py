"""Tests for Guardian: Luna's read-only liaison to Rowan.

Every test runs against a throwaway SQLite file; no network anywhere.
Guardian must never call a provider and never write outside its own
guardian_suggestions table.
"""
import pathlib

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import broker as B
from luna_v2 import guardian as G
from luna_v2 import specialists as SP
import luna_v2.guardian


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "g.db"))
    yield s
    s.close()


def _open_mission(store, title="work", steps=("one", "two")):
    m = M.create_mission(store, "jason", title, "proof")
    for desc in steps:
        M.add_step(store, "jason", m.id, desc, "routine")
    return m


# (a) stuck missions: one info suggestion, no dupes on rescan --------------
def test_stuck_mission_files_one_info_and_rescan_dedupes(store):
    m = _open_mission(store)
    new = G.scan(store, "jason")
    stuck = [r for r in new if r["check_name"] == "stuck_mission"]
    assert len(stuck) == 1
    assert stuck[0]["severity"] == "info"
    assert stuck[0]["subject"] == f"mission {m.id}"
    assert "2 of 2" in stuck[0]["observation"]
    # immediate rescan files nothing new (dedupe on open suggestions)
    assert G.scan(store, "jason") == []
    # an open mission with no steps at all is NOT flagged as stuck
    empty = M.create_mission(store, "jason", "empty", "x")
    G.scan(store, "jason")
    assert not [r for r in G.inbox(store, "jason")
                if r["subject"] == f"mission {empty.id}"]


def test_completed_mission_is_not_stuck(store):
    m = _open_mission(store)
    for s in store.list_steps(m.id):
        M.complete_step(store, s["id"], result="r", evidence="proof")
    M.close_mission(store, m.id)
    assert not [r for r in G.scan(store, "jason")
                if r["check_name"] == "stuck_mission"]


# (g) awaiting approval ------------------------------------------------------
def test_awaiting_approval_flags_unapproved_consequential_step(store):
    m = M.create_mission(store, "jason", "wait", "x")
    cs = M.add_step(store, "jason", m.id, "big move", "consequential")
    new = G.scan(store, "jason")
    ap = [r for r in new if r["check_name"] == "awaiting_approval"]
    assert len(ap) == 1
    assert ap[0]["severity"] == "info"
    assert f"step {cs.id}" == ap[0]["subject"]
    # once Jason approves, the condition clears — rescan files nothing new
    M.request_approval(store, "jason", cs.id, "approve", "fine")
    new2 = G.scan(store, "jason")
    assert not [r for r in new2 if r["check_name"] == "awaiting_approval"]


# (b) failed specialist runs -------------------------------------------------
def test_failed_run_files_warning_with_error_text(store):
    SP._ensure_schema(store)
    rid = SP._record_run(store, "scout", "jason", None, None, "q", [])
    SP._update_run(store, rid, status="failed",
                   error="boom: fetch exploded mid-run")
    new = G.scan(store, "jason")
    failed = [r for r in new if r["check_name"] == "failed_run"]
    assert len(failed) == 1
    assert failed[0]["severity"] == "warning"
    assert "boom: fetch exploded mid-run" in failed[0]["evidence"]
    assert G.scan(store, "jason") == []  # deduped


# (c) allocation burn thresholds ---------------------------------------------
def test_allocation_burn_warns_at_80_and_critical_at_95(store):
    B.add_provider(store, "jason", "testp", "calls",
                   allowance=100, period="daily")
    B.record_usage(store, "jason", "testp", "calls", 80)
    new = G.scan(store, "jason")
    burn = [r for r in new if r["check_name"] == "allocation_burn"]
    assert len(burn) == 1
    assert burn[0]["severity"] == "warning"
    assert "80.0%" in burn[0]["observation"]
    assert "80 of 100 calls" in burn[0]["evidence"]
    # resolve it, burn more: a critical files as a NEW suggestion
    G.resolve(store, burn[0]["id"], "done", "acknowledged, still burning")
    B.record_usage(store, "jason", "testp", "calls", 15)  # 95 of 100
    new = G.scan(store, "jason")
    burn2 = [r for r in new if r["check_name"] == "allocation_burn"]
    assert len(burn2) == 1
    assert burn2[0]["severity"] == "critical"
    assert "95.0%" in burn2[0]["observation"]
    # unknown-quota and retired allocations never burn-warn
    B.add_provider(store, "jason", "mystery", "tokens",
                   allowance=None, period="daily")
    B.add_provider(store, "jason", "cohere", "calls",
                   allowance=1000, period="monthly",
                   status="evaluation_only", production_allowed=0)
    new = G.scan(store, "jason")
    assert not [r for r in new if r["check_name"] == "allocation_burn"]


# (d) resolution --------------------------------------------------------------
def test_resolve_transitions_note_and_missing_id(store):
    row = G.file_suggestion(store, "jason", "stuck_mission", "mission 9",
                            "info", "obs", "ev", "act")
    assert row["status"] == "open"
    r = G.resolve(store, row["id"], "acknowledged", "looking into it")
    assert r["status"] == "acknowledged"
    assert r["resolution_note"] == "looking into it"
    assert r["resolved_at"]
    r = G.resolve(store, row["id"], "done", "fixed")
    assert r["status"] == "done" and r["resolution_note"] == "fixed"
    with pytest.raises(G.SuggestionNotFound):
        G.resolve(store, 9999, "done")
    with pytest.raises(G.BadResolution):
        G.resolve(store, row["id"], "maybe")


# (e) purity: no provider calls, no writes outside guardian_suggestions ------
def test_scan_is_read_only_over_luna_state(store, monkeypatch):
    m = _open_mission(store)
    for s in store.list_steps(m.id):
        M.complete_step(store, s["id"], result="r", evidence="proof")
    M.close_mission(store, m.id)
    B.seed_providers(store, "jason")
    B.record_usage(store, "jason", "groq", "requests", 1, note="t")
    SP._ensure_schema(store)
    tables = ["missions", "steps", "approvals", "receipts", "value_ledger",
              "broker_providers", "broker_usage", "broker_ledger",
              "specialist_runs"]
    def counts():
        return {t: store._db.execute(
            f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] for t in tables}
    before = counts()

    def _boom(*a, **k):
        raise AssertionError("guardian must never call a provider")
    monkeypatch.setattr("luna_v2.dispatch.dispatch", _boom)

    assert G.scan(store, "jason") == []  # healthy DB: nothing to file
    assert counts() == before

    # structural invariant: guardian.py never references the dispatch layer
    src = pathlib.Path(luna_v2.guardian.__file__).read_text()
    assert "dispatch" not in src


# (f) a healthy DB files zero suggestions ------------------------------------
def test_healthy_db_files_zero_suggestions(store):
    m = _open_mission(store)
    for s in store.list_steps(m.id):
        M.complete_step(store, s["id"], result="r", evidence="proof")
    M.close_mission(store, m.id)
    B.seed_providers(store, "jason")
    B.record_usage(store, "jason", "groq", "requests", 1)
    assert G.scan(store, "jason") == []
    assert G.inbox(store, "jason") == []


# inbox ordering ---------------------------------------------------------------
def test_inbox_orders_severity_then_age(store):
    w = G.file_suggestion(store, "jason", "failed_run", "run 1",
                          "warning", "o", "e", "a")
    i = G.file_suggestion(store, "jason", "stuck_mission", "mission 1",
                          "info", "o", "e", "a")
    c = G.file_suggestion(store, "jason", "allocation_burn", "x/calls",
                          "critical", "o", "e", "a")
    G.resolve(store, i["id"], "done", "finished")
    G.resolve(store, w["id"], "acknowledged", "on it")
    # done suggestions leave the inbox; acknowledged stay
    assert [r["id"] for r in G.inbox(store, "jason")] == [c["id"], w["id"]]
