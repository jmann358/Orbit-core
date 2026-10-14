"""Tests for the Marshal specialist (luna_v2/marshal.py).

The Marshal coordinates; he does not command. The tests pin: member
count bounds, refusal of retired members (no bypassing the review
system), restricted members carrying their marker, honest recording of
member errors, deterministic consensus, and — critically — no new
authority: a swarm creates no missions, spends nothing, approves
nothing.
"""

from luna_v2 import marshal as MA
from luna_v2 import specialists as SP
from luna_v2.store import Store

import pytest

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Deployment guards
# ---------------------------------------------------------------------------
def test_deploy_needs_two_to_five_members(store):
    with pytest.raises(MA.SwarmRefused):
        MA.deploy(store, OWNER, "q?", ["watchman"])
    with pytest.raises(MA.SwarmRefused):
        MA.deploy(store, OWNER, "q?", ["watchman"] * 6)
    with pytest.raises(MA.SwarmRefused):
        MA.deploy(store, OWNER, "   ", ["watchman", "guardian"])


def test_deploy_refuses_unknown_and_non_v1_members(store):
    with pytest.raises(MA.SwarmRefused):
        MA.deploy(store, OWNER, "q?", ["watchman", "nosuchagent"])
    with pytest.raises(MA.SwarmRefused):
        MA.deploy(store, OWNER, "q?", ["watchman", "builder"])
    row = MA.deploy(store, OWNER, "is the house healthy?",
                    ["watchman", "quartermaster"])
    assert row["status"] == "open"
    members = MA.swarm_members(store, OWNER, row["id"])
    assert [m["specialist"] for m in members] == ["watchman",
                                                 "quartermaster"]


def test_deploy_refuses_retired_members(store):
    # Retire a specialist through the review system's own table.
    SP._ensure_status_schema(store)  # same package; schema first
    store._db.execute(
        "INSERT INTO specialist_status (owner, specialist, status, "
        "decided_by, note, created_at) VALUES (?, 'watchman', "
        "'retired', 'jason', 'slacking', '2026-10-14T00:00:00+00:00')",
        (OWNER,))
    store._db.commit()
    with pytest.raises(MA.SwarmRefused) as exc:
        MA.deploy(store, OWNER, "q?", ["watchman", "guardian"])
    assert "retired by jason" in str(exc.value)
    assert MA.list_swarms(store, OWNER) == []  # nothing written


def test_restricted_member_carries_its_marker(store):
    SP._ensure_status_schema(store)  # same package; schema first
    store._db.execute(
        "INSERT INTO specialist_status (owner, specialist, status, "
        "decided_by, note, created_at) VALUES (?, 'watchman', "
        "'restricted', 'jason', 'under review', "
        "'2026-10-14T00:00:00+00:00')",
        (OWNER,))
    store._db.commit()
    row = MA.deploy(store, OWNER, "q?", ["watchman", "guardian"])
    member = next(m for m in MA.swarm_members(store, OWNER, row["id"])
                  if m["specialist"] == "watchman")
    assert "[restricted — under review]" in member["note"]


# ---------------------------------------------------------------------------
# Running: fan-out, recording, consensus
# ---------------------------------------------------------------------------
def test_run_swarm_records_every_member_and_closes(store):
    row = MA.deploy(store, OWNER, "is the house healthy?",
                    ["watchman", "quartermaster"])
    done = MA.run_swarm(store, OWNER, row["id"])
    assert done["status"] == "closed"
    assert "member outcomes:" in done["consensus"]
    members = MA.swarm_members(store, OWNER, row["id"])
    assert all(m["status"] == "done" for m in members)
    assert all(m["outcome"] for m in members)


def test_member_errors_are_recorded_not_hidden(store, monkeypatch):
    import luna_v2.marshal as mamod

    def boom(store, owner):
        raise RuntimeError("the member tripped")

    monkeypatch.setitem(mamod.MEMBER_RUNNERS, "watchman", boom)
    row = MA.deploy(store, OWNER, "q?", ["watchman", "guardian"])
    done = MA.run_swarm(store, OWNER, row["id"])
    assert done["status"] == "closed"
    watchman = next(m for m in MA.swarm_members(store, OWNER, row["id"])
                    if m["specialist"] == "watchman")
    assert watchman["outcome"].startswith("error: the member tripped")


def test_only_open_swarms_run(store):
    row = MA.deploy(store, OWNER, "q?", ["watchman", "guardian"])
    MA.run_swarm(store, OWNER, row["id"])
    with pytest.raises(MA.SwarmRefused):
        MA.run_swarm(store, OWNER, row["id"])
    with pytest.raises(MA.SwarmNotFound):
        MA.run_swarm(store, OWNER, 4242)


def test_majority_verdict_becomes_consensus(store, monkeypatch):
    import luna_v2.marshal as mamod

    monkeypatch.setitem(mamod.MEMBER_RUNNERS, "watchman",
                        lambda s, o: {"verdict": "healthy"})
    monkeypatch.setitem(mamod.MEMBER_RUNNERS, "guardian",
                        lambda s, o: {"status": "healthy"})
    monkeypatch.setitem(mamod.MEMBER_RUNNERS, "sentinel",
                        lambda s, o: {"status": "healthy"})
    row = MA.deploy(store, OWNER, "q?",
                    ["watchman", "guardian", "sentinel"])
    done = MA.run_swarm(store, OWNER, row["id"])
    assert "consensus: 'healthy' (3/3 members)" in done["consensus"]


def test_mixed_signals_record_contradictions(store, monkeypatch):
    import luna_v2.marshal as mamod

    monkeypatch.setitem(mamod.MEMBER_RUNNERS, "watchman",
                        lambda s, o: {"verdict": "healthy"})
    monkeypatch.setitem(mamod.MEMBER_RUNNERS, "guardian",
                        lambda s, o: {"status": "critical"})
    row = MA.deploy(store, OWNER, "q?", ["watchman", "guardian"])
    done = MA.run_swarm(store, OWNER, row["id"])
    assert "no consensus — mixed signals" in done["consensus"]
    assert "'healthy'" in done["consensus"]
    assert "'critical'" in done["consensus"]


# ---------------------------------------------------------------------------
# No new authority
# ---------------------------------------------------------------------------
def test_swarm_creates_no_missions_spends_nothing(store):
    missions_before = store._db.execute(
        "SELECT COUNT(*) AS n FROM missions").fetchone()["n"]
    usage_before = store._db.execute(
        "SELECT COUNT(*) AS n FROM broker_usage").fetchone()["n"]
    row = MA.deploy(store, OWNER, "is the house healthy?",
                    ["watchman", "quartermaster", "guardian"])
    MA.run_swarm(store, OWNER, row["id"])
    missions_after = store._db.execute(
        "SELECT COUNT(*) AS n FROM missions").fetchone()["n"]
    usage_after = store._db.execute(
        "SELECT COUNT(*) AS n FROM broker_usage").fetchone()["n"]
    assert missions_after == missions_before
    assert usage_after == usage_before
