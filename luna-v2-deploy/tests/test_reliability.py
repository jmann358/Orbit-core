"""Reliability pack (P0-5): restart durability and ledger integrity.

Every test runs against a real on-disk SQLite file and simulates a
process restart by closing the Store and opening a brand-new Store on
the same file. No network anywhere.
"""

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import dispatch as D
from luna_v2 import missions as M

OWNER = "jason"


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "restart.db")


def _seeded(db_path):
    s = Store(db_path)
    B.seed_providers(s, OWNER)
    return s


# -- (a) restart durability: full mission lifecycle -------------------------
def test_restart_durability_mission_lifecycle(db_path):
    s = Store(db_path)
    mission = M.create_mission(s, OWNER, "restart drill",
                               "prove state survives a restart")
    r_step = M.add_step(s, OWNER, mission.id, "routine bit", M.ROUTINE)
    c_step = M.add_step(s, OWNER, mission.id, "consequential bit",
                        M.CONSEQUENTIAL)
    M.complete_step(s, r_step.id, "routine done", "evidence: routine output")
    M.request_approval(s, OWNER, c_step.id, "approve", "go ahead")
    s.close()

    # a full process restart: brand-new Store on the same file
    s2 = Store(db_path)
    reopened = s2.get_mission(mission.id)
    assert reopened["title"] == "restart drill"
    assert reopened["status"] == M.MISSION_OPEN
    assert reopened["outcome"] == "prove state survives a restart"
    steps = s2.list_steps(mission.id)
    assert [(st["kind"], st["status"]) for st in steps] == [
        (M.ROUTINE, M.STEP_DONE), (M.CONSEQUENTIAL, M.STEP_OPEN)]
    assert steps[0]["evidence"] == "evidence: routine output"
    approvals = s2.list_approvals(c_step.id)
    assert len(approvals) == 1
    assert approvals[-1]["decision"] == "approve"
    assert approvals[-1]["reason"] == "go ahead"
    # the approval gate still holds after the restart: finishing works
    finished = M.complete_step(s2, c_step.id, "consequential done",
                               "evidence: approved output")
    assert finished.status == M.STEP_DONE
    receipt = M.close_mission(s2, mission.id)
    assert receipt.summary.startswith("Mission 'restart drill' closed: "
                                      "2 done, 0 skipped.")
    s2.close()


# -- (b) restart durability: broker usage + ledger ---------------------------
def test_restart_durability_broker_ledger(db_path):
    s = _seeded(db_path)
    B.record_usage(s, OWNER, "groq", "requests", 3.0, note="reliability drill")
    B.record_usage(s, OWNER, "groq", "tokens", 400.0, note="reliability drill")
    before_used = {(a.provider, a.unit): a.used
                   for a in B.list_allocations(s, OWNER)}
    before_totals = sorted(
        (t["provider"], t["unit"], t["total_used"])
        for t in s.ledger_totals(OWNER))
    s.close()

    s2 = Store(db_path)
    after_used = {(a.provider, a.unit): a.used
                  for a in B.list_allocations(s2, OWNER)}
    after_totals = sorted(
        (t["provider"], t["unit"], t["total_used"])
        for t in s2.ledger_totals(OWNER))
    assert after_used == before_used
    assert after_totals == before_totals
    assert after_used[("groq", "requests")] == 3.0
    assert after_used[("groq", "tokens")] == 400.0
    # the store is still fully usable after the restart
    B.record_usage(s2, OWNER, "groq", "tokens", 100.0)
    assert {(a.provider, a.unit): a.used
            for a in B.list_allocations(s2, OWNER)}[("groq", "tokens")] == 500.0
    s2.close()


# -- (c) interrupted dispatch -------------------------------------------------
# Covered by tests/test_dispatch.py::test_transport_failure_records_nothing:
# a transport that raises mid-call leaves zero usage and zero ledger rows.
# That coverage is not duplicated here.


# -- (d) two stores, one file, interleaved writes -----------------------------
def test_two_stores_interleaved_usage_sums_exactly(db_path):
    s1 = _seeded(db_path)
    s2 = Store(db_path)
    expected = 0.0
    for i in range(10):
        amt1 = 100.0 + i
        B.record_usage(s1, OWNER, "groq", "tokens", amt1, note=f"s1-{i}")
        amt2 = 50.0 + 10 * i
        B.record_usage(s2, OWNER, "groq", "tokens", amt2, note=f"s2-{i}")
        expected += amt1 + amt2
    s1.close()
    s2.close()

    s3 = Store(db_path)
    row = s3._db.execute(
        "SELECT COUNT(*) AS n, SUM(amount) AS total FROM broker_usage "
        "WHERE owner = ? AND provider = ? AND unit = ?",
        (OWNER, "groq", "tokens")).fetchone()
    assert row["n"] == 20
    assert row["total"] == expected
    ledger = s3._db.execute(
        "SELECT COUNT(*) AS n, SUM(amount) AS total FROM broker_ledger "
        "WHERE owner = ? AND provider = ? AND unit = ?",
        (OWNER, "groq", "tokens")).fetchone()
    assert ledger["n"] == 20
    assert ledger["total"] == expected
    s3.close()


# -- (e) receipt integrity across a restart ------------------------------------
def test_receipt_identical_across_restart(db_path):
    s = Store(db_path)
    mission = M.create_mission(s, OWNER, "receipt drill")
    step = M.add_step(s, OWNER, mission.id, "do the thing", M.ROUTINE)
    M.complete_step(s, step.id, "result", "evidence")
    M.close_mission(s, mission.id)
    before = s.get_receipt(mission.id)
    before_pair = (before["summary"], before["evidence_json"])
    s.close()

    s2 = Store(db_path)
    after = s2.get_receipt(mission.id)
    assert (after["summary"], after["evidence_json"]) == before_pair
    assert M.Receipt(after).summary == before["summary"]
    assert M.Receipt(after).evidence == M.Receipt(before).evidence
    s2.close()
