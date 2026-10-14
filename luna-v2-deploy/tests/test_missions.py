"""Tests for the Luna v2 mission skeleton."""

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _planned(store, n_routine=1, n_consequential=1):
    m = M.create_mission(store, OWNER, "demo", outcome="proof of concept")
    steps = []
    for i in range(n_routine):
        steps.append(M.add_step(store, OWNER, m.id, f"routine {i}", "routine"))
    for i in range(n_consequential):
        steps.append(
            M.add_step(store, OWNER, m.id, f"consequential {i}", "consequential"))
    return m, steps


def test_full_happy_path(store):
    m, (r, c) = _planned(store)
    # routine step completes with evidence
    s1 = M.complete_step(store, r.id, "done", "logs show pass")
    assert s1.status == "done"
    # consequential step is blocked before approval
    with pytest.raises(M.StepNotApproved):
        M.complete_step(store, c.id, "done", "email sent")
    # approving a routine step is refused
    with pytest.raises(M.StepNotConsequential):
        M.request_approval(store, OWNER, r.id, "approve")
    # reject first: latest decision governs, step still blocked
    M.request_approval(store, OWNER, c.id, "reject", "draft was wrong")
    assert not M.is_approved(store, c)
    with pytest.raises(M.StepNotApproved):
        M.complete_step(store, c.id, "done", "email sent")
    # approve -> completes
    M.request_approval(store, OWNER, c.id, "approve", "looks good now")
    assert M.is_approved(store, c)
    s2 = M.complete_step(store, c.id, "email sent", "message id 42 in outbox")
    assert s2.status == "done"
    # approval history is append-only and readable
    hist = store.list_approvals(c.id)
    assert [a["decision"] for a in hist] == ["reject", "approve"]
    # close creates the receipt
    rc = M.close_mission(store, m.id)
    assert rc.mission_id == m.id
    assert rc.owner == OWNER
    assert "closed" in rc.summary
    assert store.get_mission(m.id)["status"] == "closed"
    # value can now be logged
    vid = M.log_value(store, m.id, "hours", 0.5, "would take 30 min by hand")
    assert vid > 0
    rows = store.list_value(m.id)
    assert len(rows) == 1 and rows[0]["amount"] == 0.5
    assert store.value_totals(OWNER) == {"hours": 0.5}


def test_close_fails_with_open_steps(store):
    m, (r, c) = _planned(store)
    M.complete_step(store, r.id, "done", "evidence")
    with pytest.raises(M.MissionNotClosable):
        M.close_mission(store, m.id)


def test_skip_unblocks_close(store):
    m, (r, c) = _planned(store)
    M.complete_step(store, r.id, "done", "evidence")
    M.skip_step(store, c.id, "no longer needed")
    rc = M.close_mission(store, m.id)
    assert rc.evidence["steps_skipped"] == 1


def test_evidence_required(store):
    m, (r, _) = _planned(store)
    with pytest.raises(M.LunaError):
        M.complete_step(store, r.id, "done", "   ")


def test_value_requires_closed_mission(store):
    m, (r, _) = _planned(store)
    with pytest.raises(M.ValueBeforeClose):
        M.log_value(store, m.id, "hours", 1, "baseline")


def test_owner_stored_on_every_record(store):
    m, (r, c) = _planned(store)
    assert m.owner == OWNER
    assert r.owner == OWNER and c.owner == OWNER
    M.request_approval(store, OWNER, c.id, "approve")
    approvals = store.list_approvals(c.id)
    assert all(a["owner"] == OWNER for a in approvals)
    M.complete_step(store, r.id, "done", "e")
    M.complete_step(store, c.id, "done", "e")
    rc = M.close_mission(store, m.id)
    assert rc.owner == OWNER
    M.log_value(store, m.id, "money", 12.5, "would cost $12.50 otherwise")
    v = store.list_value(m.id)[0]
    assert v["owner"] == OWNER


def test_not_found_errors(store):
    with pytest.raises(M.NotFound):
        M.complete_step(store, 999, "x", "e")
    with pytest.raises(M.NotFound):
        M.close_mission(store, 999)


def test_invalid_inputs(store):
    with pytest.raises(M.LunaError):
        M.create_mission(store, OWNER, "   ")
    m = M.create_mission(store, OWNER, "t")
    with pytest.raises(M.LunaError):
        M.add_step(store, OWNER, m.id, "x", "magical")
    with pytest.raises(M.LunaError):
        M.log_value(store, m.id, "minutes", 1, "b")
