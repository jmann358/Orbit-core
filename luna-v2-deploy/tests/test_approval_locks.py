"""Tests for Jason's approval-lock rule (2026-10-14).

A rejection ELEVATES concern — it is never silently overwritten.
A security/risk rejection LOCKS the step: it may only proceed on an
approval that explicitly acknowledges the recorded risks. Non-risk
rejections keep the old latest-decision-wins behavior. The
completion gate in missions.complete_step is the authoritative
enforcement (not just the CLI).
"""

import pytest

from luna_v2 import missions as M
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _consequential(store):
    mid = store.create_mission(OWNER, "Lock probe", "")
    sid = store.add_step(mid, OWNER, "spend real money", "consequential", 1)
    return sid


def test_risk_rejection_then_plain_approval_completing_raises(store):
    sid = _consequential(store)
    reason = "this endpoint looked compromised — unknown cert"
    M.request_approval(store, OWNER, sid, "reject", reason, category="risk")
    M.request_approval(store, OWNER, sid, "approve", "on second thought")
    with pytest.raises(M.LunaError, match="locked") as ei:
        M.complete_step(store, sid, "done", "evidence")
    assert reason in str(ei.value)  # the specific risk is shown verbatim
    assert store.get_step(sid)["status"] == "open"


def test_risk_rejection_then_acknowledged_approval_completes(store):
    sid = _consequential(store)
    M.request_approval(store, OWNER, sid, "reject", "unknown cert",
                       category="risk")
    M.request_approval(store, OWNER, sid, "approve",
                       "accepting the cert risk after review",
                       risk_ack=True)
    step = M.complete_step(store, sid, "done", "evidence")
    assert step.status == "done"


def test_security_category_locks_the_same_way(store):
    sid = _consequential(store)
    M.request_approval(store, OWNER, sid, "reject", "phishing domain",
                       category="security")
    M.request_approval(store, OWNER, sid, "approve")
    with pytest.raises(M.LunaError, match="locked"):
        M.complete_step(store, sid, "done", "evidence")
    M.request_approval(store, OWNER, sid, "approve", "domain verified",
                       risk_ack=True)
    assert M.complete_step(store, sid, "done", "evidence").status == "done"


def test_non_risk_rejection_keeps_latest_decision_wins(store):
    sid = _consequential(store)
    M.request_approval(store, OWNER, sid, "reject", "typo in the plan",
                       category="mistake")
    M.request_approval(store, OWNER, sid, "approve", "fixed the typo")
    assert M.complete_step(store, sid, "done", "evidence").status == "done"


def test_not_now_rejection_keeps_old_behavior(store):
    sid = _consequential(store)
    M.request_approval(store, OWNER, sid, "reject", "wait for Jason",
                       category="not_now")
    M.request_approval(store, OWNER, sid, "approve", "he said go")
    assert M.complete_step(store, sid, "done", "evidence").status == "done"


def test_step_lock_info_reports_lock_and_reasons(store):
    sid = _consequential(store)
    info = M.step_lock_info(store, sid)
    assert info == {"locked": False, "reasons": []}
    M.request_approval(store, OWNER, sid, "reject", "shady redirect",
                       category="risk")
    M.request_approval(store, OWNER, sid, "reject", "also expired token",
                       category="security")
    info = M.step_lock_info(store, sid)
    assert info["locked"] is True
    assert info["reasons"] == ["shady redirect", "also expired token"]


def test_legacy_approval_rows_without_category_do_not_lock(store):
    sid = _consequential(store)
    # bypass request_approval to simulate a row from before categories
    store._db.execute(
        "INSERT INTO approvals (step_id, owner, decision, reason, "
        "category, risk_ack, decided_at) VALUES (?, ?, 'reject', "
        "'old row', 'other', 0, '2026-01-01T00:00:00')", (sid, OWNER))
    store._db.execute(
        "INSERT INTO approvals (step_id, owner, decision, reason, "
        "category, risk_ack, decided_at) VALUES (?, ?, 'approve', "
        "'old row', 'other', 0, '2026-01-02T00:00:00')", (sid, OWNER))
    store._db.commit()
    assert M.step_lock_info(store, sid)["locked"] is False
    assert M.complete_step(store, sid, "done", "evidence").status == "done"


def test_bad_category_is_refused(store):
    sid = _consequential(store)
    with pytest.raises(M.LunaError):
        M.request_approval(store, OWNER, sid, "reject", "x",
                           category="nonsense")
