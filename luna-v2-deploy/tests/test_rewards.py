"""Tests for Mentor-administered rewards (the golden-buzzer system).

Jason's design, 2026-10-14: Mentor — who already grades the team —
also administers rewards. Four tiers; no punishment system; the
ledger is append-only; Mentor can never reward itself; every grant
cites verified evidence; Rowan's cross-check quarantines mismatches
visibly.
"""
import re

import pytest

from luna_v2.store import Store
from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2 import rewards as R
from luna_v2 import verifier as V


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "rewards.db"))
    yield s
    s.close()


def _closed_mission(store, owner="jason", title="proof"):
    m = M.create_mission(store, owner, title, "outcome")
    step = M.add_step(store, owner, m.id, "a step", "routine")
    M.complete_step(store, step.id, "done", "evidence")
    M.close_mission(store, m.id)
    return m


def _verifier_pass(store, mission_id, owner="jason"):
    V._ensure_schema(store)
    row = store._db.execute(
        "INSERT INTO verification_runs (owner, mission_id, verdict, "
        "checks_json, created_at) VALUES (?, ?, 'pass', '[]', "
        "datetime('now'))", (owner, mission_id))
    store._db.commit()
    return row.lastrowid


def test_all_fifteen_currencies_listed():
    cs = R.currencies()
    assert len(cs) == 15
    names = {c["specialist"] for c in cs}
    assert names == {"scout", "verifier", "builder", "quartermaster",
                     "archivist", "watchman", "envoy", "designer",
                     "guardian", "armorer", "scheduler", "operator",
                     "mentor", "sentinel", "host"}
    by = {c["specialist"]: c for c in cs}
    assert by["scout"]["currency"] == "Research Credits"
    assert by["scout"]["monthly_cap"] == 30
    assert by["guardian"]["currency"] == "Commendation Seals"
    assert by["operator"]["currency"] == "Maintenance Priority Credits"
    assert by["mentor"]["currency"] == "Honorary Mentor Badges"
    assert by["mentor"]["monthly_cap"] is None


def test_cosmetic_grant_happy_path(store):
    m = _closed_mission(store)
    row = R.grant(store, "jason", "scout", "cosmetic", 1,
                  "mission", m.id, granted_by="mentor",
                  note="Scout-Star")
    assert row["specialist"] == "scout"
    assert row["tier"] == "cosmetic"
    assert row["amount"] == 1
    assert row["status"] == "active"
    assert row["currency"] == "Research Credits"
    assert row["expires_at"]  # cosmetic defaults to a 90-day term


def test_cosmetic_amount_must_be_one(store):
    m = _closed_mission(store)
    with pytest.raises(R.RewardsError):
        R.grant(store, "jason", "scout", "cosmetic", 3,
                "mission", m.id)


def test_grant_refuses_unverified_evidence(store):
    m = M.create_mission(store, "jason", "still open", "outcome")
    with pytest.raises(R.EvidenceMissing) as e:
        R.grant(store, "jason", "scout", "cosmetic", 1,
                "mission", m.id)
    assert "not closed" in str(e.value)
    with pytest.raises(R.EvidenceMissing):
        R.grant(store, "jason", "scout", "cosmetic", 1,
                "mission", 99999)


def test_resource_cap_enforced(store):
    m = _closed_mission(store)
    # builder cap is 20: 12 + 8 fits exactly, one more unit refuses
    R.grant(store, "jason", "builder", "resource", 12,
            "mission", m.id, note="batch one")
    R.grant(store, "jason", "builder", "resource", 8,
            "mission", m.id, note="batch two")
    assert R.month_resource_total(store, "jason", "builder") == 20
    with pytest.raises(R.CapExceeded) as e:
        R.grant(store, "jason", "builder", "resource", 1,
                "mission", m.id)
    msg = str(e.value)
    assert "20 already this month + 1 requested > 20" in msg


def test_permission_and_ticket_cannot_be_granted_directly(store):
    m = _closed_mission(store)
    for tier in ("permission", "goldenticket"):
        with pytest.raises(R.RewardsError) as e:
            R.grant(store, "jason", "envoy", tier, 1,
                    "mission", m.id)
        assert "cannot be granted directly" in str(e.value)


def test_self_dealing_ban(store):
    m = _closed_mission(store)
    # Mentor granting itself even a cosmetic badge: refused
    with pytest.raises(R.SelfDealing):
        R.grant(store, "jason", "mentor", "cosmetic", 1,
                "mission", m.id, granted_by="mentor")
    # Jason may grant Mentor a cosmetic badge
    row = R.grant(store, "jason", "mentor", "cosmetic", 1,
                  "mission", m.id, granted_by="jason",
                  note="good grading this week")
    assert row["granted_by"] == "jason"
    assert row["currency"] == "Honorary Mentor Badges"
    # Nobody may grant Mentor anything but a cosmetic badge
    with pytest.raises(R.SelfDealing):
        R.grant(store, "jason", "mentor", "resource", 1,
                "mission", m.id, granted_by="jason")
    # Rowan granting Mentor a badge IS allowed — prove it
    ok = R.grant(store, "jason", "mentor", "cosmetic", 1,
                 "mission", m.id, granted_by="rowan",
                 note="badges from rowan")
    assert ok["granted_by"] == "rowan"


def test_recommendation_cannot_self_apply(store):
    m = _closed_mission(store)
    rec = R.recommend_permission(store, "jason", "envoy",
                                 "lead the next treaty",
                                 "mission", m.id)
    assert rec["status"] == "pending"
    assert rec["recommended_by"] == "mentor"
    # nothing landed in the ledger
    assert R.active_permission_count(store, "jason", "envoy") == 0
    assert R.list_rewards(store, "jason", "envoy") == []


def test_permission_decision_flow(store):
    m = _closed_mission(store)
    rec = R.recommend_permission(store, "jason", "envoy",
                                 "lead the next treaty",
                                 "mission", m.id)
    # only Jason may decide
    with pytest.raises(R.NotDecided):
        R.decide_request(store, "jason", "recommendation", rec["id"],
                         "approve", decided_by="rowan")
    # decline writes nothing
    assert R.decide_request(store, "jason", "recommendation",
                            rec["id"], "decline") is None
    assert R.active_permission_count(store, "jason", "envoy") == 0
    # approve applies exactly one ledger row, granted_by=jason
    rec2 = R.recommend_permission(store, "jason", "envoy",
                                  "lead the next treaty",
                                  "mission", m.id)
    row = R.decide_request(store, "jason", "recommendation",
                           rec2["id"], "approve", note="earned it")
    assert row["tier"] == "permission"
    assert row["granted_by"] == "jason"
    assert row["specialist"] == "envoy"
    assert R.active_permission_count(store, "jason", "envoy") == 1


def test_permission_five_active_ceiling(store):
    m = _closed_mission(store)
    for i in range(5):
        rec = R.recommend_permission(store, "jason", "envoy",
                                     f"freedom {i}", "mission", m.id)
        R.decide_request(store, "jason", "recommendation",
                         rec["id"], "approve")
    rec = R.recommend_permission(store, "jason", "envoy",
                                 "one too many", "mission", m.id)
    with pytest.raises(R.CapExceeded) as e:
        R.decide_request(store, "jason", "recommendation",
                         rec["id"], "approve")
    assert "5 active permission rewards" in str(e.value)


def test_golden_ticket_quota_and_flow(store):
    m = _closed_mission(store)
    t1 = R.request_golden_ticket(store, "jason", "scout",
                                 "double research cap",
                                 "mission", m.id)
    assert t1["status"] == "pending"
    # second request this quarter refuses
    with pytest.raises(R.QuotaExceeded) as e:
        R.request_golden_ticket(store, "jason", "scout",
                                "more of everything",
                                "mission", m.id)
    assert "this quarter" in str(e.value)
    # request itself granted nothing
    assert R.list_rewards(store, "jason", "scout") == []
    # Jason's approval writes the fast-track ledger row
    row = R.decide_request(store, "jason", "ticket", t1["id"],
                           "approve", note="golden buzzer")
    assert row["tier"] == "goldenticket"
    assert row["granted_by"] == "jason"
    assert "every gate still applies" in row["note"]


def test_cross_check_quarantines_forged_evidence(store):
    m = _closed_mission(store)
    good = R.grant(store, "jason", "scout", "cosmetic", 1,
                   "mission", m.id)
    # sneak a row in behind the API with a bogus mission id
    cur = store._db.execute(
        "INSERT INTO reward_ledger (grant_key, owner, created_at, "
        "specialist, currency, tier, amount, granted_by, evidence_kind, "
        "evidence_id, status, note) VALUES (?, ?, ?, 'watchman', "
        "'Surveillance Hours', 'cosmetic', 1, 'mentor', 'mission', "
        "424242, 'active', '')",
        ("forgedkey", "jason", "2026-10-14T00:00:00+00:00"))
    store._db.commit()
    bad_id = cur.lastrowid
    findings = R.cross_check(store, "jason")
    assert len(findings) == 1
    assert findings[0]["reward_id"] == bad_id
    assert R.is_quarantined(store, "jason", bad_id)
    # the good row is untouched and NOT quarantined
    assert not R.is_quarantined(store, "jason", good["id"])
    # a Guardian suggestion was filed — the quarantine is visible
    inbox = [s for s in G.inbox(store, "jason")
             if s["check_name"] == "rewards_crosscheck"]
    assert inbox and "mismatch" in inbox[0]["observation"].lower()
    # rerunning the check does not double-file the flag
    assert R.cross_check(store, "jason") == []
    # and the flagged row is still there — never silently deleted
    assert R.get_ledger_row(store, "jason", bad_id)["id"] == bad_id


def test_quarantine_can_be_cleared_by_jason(store):
    m = _closed_mission(store)
    R._ensure_schema(store)
    cur = store._db.execute(
        "INSERT INTO reward_ledger (grant_key, owner, created_at, "
        "specialist, currency, tier, amount, granted_by, evidence_kind, "
        "evidence_id, status, note) VALUES (?, ?, ?, 'watchman', "
        "'Surveillance Hours', 'cosmetic', 1, 'mentor', 'mission', "
        "424242, 'active', '')",
        ("forgedkey2", "jason", "2026-10-14T00:00:00+00:00"))
    store._db.commit()
    bad_id = cur.lastrowid
    R.cross_check(store, "jason")
    assert R.is_quarantined(store, "jason", bad_id)
    R.clear_flag(store, "jason", bad_id, by_whom="jason")
    assert not R.is_quarantined(store, "jason", bad_id)
    # clearing is itself a new row — the quarantine row still exists
    flags = store._db.execute(
        "SELECT flag FROM reward_flags WHERE owner = ? AND reward_id = ? "
        "ORDER BY id", ("jason", bad_id)).fetchall()
    assert [f["flag"] for f in flags] == ["quarantined", "cleared"]


def test_ledger_is_append_only(store):
    m = _closed_mission(store)
    # a term already in the past so the expiry job picks it up now
    row = R.grant(store, "jason", "scout", "cosmetic", 1,
                  "mission", m.id,
                  expires_at="2026-10-01T00:00:00+00:00")
    # expiry appends; the original row is untouched
    rows_before = store._db.execute(
        "SELECT COUNT(*) FROM reward_ledger").fetchone()[0]
    n = R.expire_rewards(store, "jason")
    assert n == 1
    rows_after = store._db.execute(
        "SELECT COUNT(*) FROM reward_ledger").fetchone()[0]
    assert rows_after == rows_before + 1
    orig = R.get_ledger_row(store, "jason", row["id"])
    assert orig["status"] == "active"  # original row unchanged
    live = R.list_rewards(store, "jason", "scout")
    assert live[0]["status"] == "expired"
    # the module never UPDATEs or DELETEs ledger rows
    src = open(__import__("luna_v2.rewards", fromlist=["__file__"])
               .__file__).read()
    assert not re.search(r"\bUPDATE\s+reward_ledger\b", src)
    assert not re.search(r"\bDELETE\s+FROM\s+reward_ledger\b", src)


def test_rotation_is_valid_evidence(store):
    rot = R.record_rotation(store, "jason", "watchman",
                            "scenario: midnight alert drill")
    ok, why = R.evidence_ok(store, "rotation", rot["id"])
    assert ok, why
    # and a grant can cite it — rotations are neutral learning rounds
    row = R.grant(store, "jason", "watchman", "resource", 2,
                  "rotation", rot["id"])
    assert row["tier"] == "resource"
    assert row["amount"] == 2


def test_verifier_pass_evidence(store):
    m = _closed_mission(store)
    run_id = _verifier_pass(store, m.id)
    row = R.grant(store, "jason", "builder", "resource", 4,
                  "verifier_run", run_id)
    assert row["currency"] == "Build-Priority Points"
    # a FAILED verifier run is not evidence
    V._ensure_schema(store)
    cur = store._db.execute(
        "INSERT INTO verification_runs (owner, mission_id, verdict, "
        "checks_json, created_at) VALUES ('jason', ?, 'fail', '[]', "
        "datetime('now'))", (m.id,))
    store._db.commit()
    with pytest.raises(R.EvidenceMissing):
        R.grant(store, "jason", "builder", "resource", 1,
                "verifier_run", cur.lastrowid)


def test_unknown_specialist_refused(store):
    m = _closed_mission(store)
    with pytest.raises(R.RewardsError):
        R.grant(store, "jason", "janitor", "cosmetic", 1,
                "mission", m.id)


def test_list_rewards_shows_quarantine(store):
    m = _closed_mission(store)
    good = R.grant(store, "jason", "scout", "cosmetic", 1,
                   "mission", m.id)
    rows = R.list_rewards(store, "jason")
    assert len(rows) == 1
    assert rows[0]["quarantined"] is False
    cur = store._db.execute(
        "INSERT INTO reward_ledger (grant_key, owner, created_at, "
        "specialist, currency, tier, amount, granted_by, evidence_kind, "
        "evidence_id, status, note) VALUES (?, ?, ?, 'envoy', "
        "'Diplomatic Influence Points', 'cosmetic', 1, 'mentor', "
        "'mission', 31337, 'active', '')",
        ("forgedkey3", "jason", "2026-10-14T00:00:00+00:00"))
    store._db.commit()
    R.cross_check(store, "jason")
    flagged = [r for r in R.list_rewards(store, "jason")
               if r["id"] == cur.lastrowid][0]
    assert flagged["quarantined"] is True
    # filtering quarantined rows hides it (but it is never deleted)
    clean = [r["id"] for r in R.list_rewards(
        store, "jason", include_quarantined=False)]
    assert good["id"] in clean
    assert cur.lastrowid not in clean
