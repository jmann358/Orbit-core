"""Tests for the Headhunter: the hiring agent's hard rules.

Headhunter prowls for S-tier talent. His guards are all proven here:
the LICENSE gate (adopt needs a permissive license — at add time and
at every later edit, never smuggled in via a two-step change), the
Envoy-style lifecycle, the Mentor-style decide discipline (he proposes;
Jason or Rowan decides), the gate-scan requirement for hiring, and the
probation machinery (one Guardian suggestion per past-due probation,
closed only by Jason or Rowan).
"""
import os
import tempfile
from datetime import datetime, timezone

import pytest

from luna_v2.store import Store
from luna_v2 import headhunter as HH
from luna_v2 import guardian as G

OWNER = "jason"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _cand(store, name="test-agent", recommendation="study", license=""):
    return HH.add_candidate(store, OWNER, name, kind="specialist",
                            tier="S", source_url="https://example.com/x",
                            license=license, recommendation=recommendation)


# ---------------------------------------------------------------------------
# The license gate
# ---------------------------------------------------------------------------

def test_adopt_refused_with_gpl_license(store):
    with pytest.raises(HH.LicenseGateRefused):
        HH.add_candidate(store, OWNER, "gpl-thing", kind="code", tier="A",
                         license="GPL-3.0", recommendation="adopt")
    assert HH.list_candidates(store, OWNER) == []


def test_adopt_refused_with_blank_license(store):
    with pytest.raises(HH.LicenseGateRefused):
        _cand(store, name="blank-lic", license="", recommendation="adopt")


def test_adopt_refused_with_unknown_license(store):
    with pytest.raises(HH.LicenseGateRefused):
        _cand(store, name="mystery-lic", license="SomeCorp EULA v9",
              recommendation="adopt")


def test_adopt_allowed_with_mit(store):
    row = _cand(store, name="mit-thing", license="MIT",
                recommendation="adopt")
    assert row["recommendation"] == "adopt"


def test_study_needs_no_license(store):
    row = _cand(store, name="proprietary-thing", license="Proprietary",
                recommendation="study")
    assert row["recommendation"] == "study"


def test_upgrade_to_adopt_at_vet_time_refused(store):
    row = _cand(store, name="sneaky", license="GPL-3.0")
    with pytest.raises(HH.LicenseGateRefused):
        HH.set_recommendation(store, row["id"], OWNER, "adopt")
    # The failed upgrade changed nothing.
    assert HH._row(store, row["id"], OWNER)["recommendation"] == "study"


def test_upgrade_to_adopt_allowed_with_permissive_license(store):
    row = _cand(store, name="legit", license="Apache-2.0")
    row = HH.set_recommendation(store, row["id"], OWNER, "adopt")
    assert row["recommendation"] == "adopt"


def test_license_downgrade_while_adopt_refused(store):
    row = _cand(store, name="flipper", license="MIT",
                recommendation="adopt")
    with pytest.raises(HH.LicenseGateRefused):
        HH.set_license(store, row["id"], OWNER, "GPL-3.0")
    assert HH._row(store, row["id"], OWNER)["license"] == "MIT"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def test_full_lifecycle_path(store):
    row = _cand(store, name="hire-me")
    row = HH.advance(store, row["id"], OWNER, "vetted")
    assert row["status"] == "vetted"
    row = HH.advance(store, row["id"], OWNER, "proposed")
    row = HH.decide(store, row["id"], OWNER, "approve", decided_by="jason")
    assert row["status"] == "approved" and row["decided_by"] == "jason"
    row = HH.mark_hired(store, row["id"], OWNER,
                        gate_scan_ref="warden scan 42: pass")
    assert row["status"] == "hired"
    assert "warden scan 42" in row["decision_note"]


def test_illegal_transitions_raise(store):
    row = _cand(store, name="jump")
    with pytest.raises(HH.InvalidTransition):
        HH.advance(store, row["id"], OWNER, "proposed")  # found→proposed
    row = HH.advance(store, row["id"], OWNER, "vetted")
    with pytest.raises(HH.InvalidTransition):
        HH.advance(store, row["id"], OWNER, "hired")  # vetted→hired


def test_rejection_path(store):
    row = _cand(store, name="nope")
    row = HH.advance(store, row["id"], OWNER, "vetted")
    row = HH.decide(store, row["id"], OWNER, "reject", decided_by="rowan",
                    note="too risky")
    assert row["status"] == "rejected"
    with pytest.raises(HH.InvalidTransition):
        HH.decide(store, row["id"], OWNER, "approve", decided_by="jason")


def test_decide_refuses_blank_decider(store):
    row = _cand(store, name="dec-blank")
    row = HH.advance(store, row["id"], OWNER, "vetted")
    with pytest.raises(HH.HeadhunterDecideRefused):
        HH.decide(store, row["id"], OWNER, "approve", decided_by="  ")


def test_decide_refuses_headhunter_itself(store):
    row = _cand(store, name="dec-self")
    row = HH.advance(store, row["id"], OWNER, "vetted")
    with pytest.raises(HH.HeadhunterDecideRefused):
        HH.decide(store, row["id"], OWNER, "approve", decided_by="Headhunter")


def test_hire_refuses_blank_gate_ref(store):
    row = _cand(store, name="no-scan")
    row = HH.advance(store, row["id"], OWNER, "vetted")
    row = HH.advance(store, row["id"], OWNER, "proposed")
    row = HH.decide(store, row["id"], OWNER, "approve", decided_by="jason")
    with pytest.raises(HH.GateScanMissing):
        HH.mark_hired(store, row["id"], OWNER, gate_scan_ref="   ")
    assert HH._row(store, row["id"], OWNER)["status"] == "approved"


# ---------------------------------------------------------------------------
# Probation
# ---------------------------------------------------------------------------

def _past_due_probation(store, specialist="probation-newbie"):
    row = HH.start_probation(store, OWNER, specialist, days=30)
    past = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    store._db.execute("UPDATE probation SET review_due = ? WHERE id = ?",
                     (past, row["id"]))
    store._db.commit()
    return row


def test_probation_due_files_exactly_one_suggestion_across_two_calls(store):
    _past_due_probation(store)
    due = HH.probation_due(store, OWNER)
    assert len(due) == 1
    count = store._db.execute(
        "SELECT COUNT(*) FROM guardian_suggestions "
        "WHERE check_name = 'probation_review' AND status = 'open'"
    ).fetchone()[0]
    assert count == 1
    # Second call files nothing new — the open one dedupes.
    HH.probation_due(store, OWNER)
    count2 = store._db.execute(
        "SELECT COUNT(*) FROM guardian_suggestions "
        "WHERE check_name = 'probation_review' AND status = 'open'"
    ).fetchone()[0]
    assert count2 == 1


def test_close_probation_by_mentor_refused(store):
    row = _past_due_probation(store, specialist="mentor-victim")
    with pytest.raises(HH.HeadhunterDecideRefused):
        HH.close_probation(store, row["id"], OWNER, "failed", by="mentor")


def test_close_probation_by_jason(store):
    row = _past_due_probation(store, specialist="graduate")
    row = HH.close_probation(store, row["id"], OWNER, "passed", by="Jason")
    assert row["status"] == "passed"
    with pytest.raises(HH.HeadhunterError):
        HH.close_probation(store, row["id"], OWNER, "passed", by="jason")


def test_probation_due_quiet_when_nothing_past_due(store):
    HH.start_probation(store, OWNER, "fresh-hire", days=30)
    assert HH.probation_due(store, OWNER) == []
    G._ensure_schema(store)
    count = store._db.execute(
        "SELECT COUNT(*) FROM guardian_suggestions").fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# Conductor tie-in: talent_hunt belongs to headhunter
# ---------------------------------------------------------------------------

def test_talent_hunt_kind_belongs_to_headhunter():
    from luna_v2 import conductor as CO
    assert "talent_hunt" in CO.MISSION_KINDS
    assert CO.MISSION_OWNER["talent_hunt"] == "headhunter"


def test_talent_hunt_tick_creates_headhunter_mission(store):
    from luna_v2 import conductor as CO
    CO.add_backlog(store, OWNER, "Talent hunt: survey S-tier agent frameworks",
                   "talent_hunt", created_by="test", origin="standing")
    out = CO.tick(store, OWNER, max_assignments=1)
    assert len(out["assigned"]) == 1
    assert out["assigned"][0]["specialist"] == "headhunter"
    assert out["assigned"][0]["how"] == "mission"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_headhunter_registry_profile():
    from luna_v2 import specialists as SP
    p = SP.get_profile("headhunter")
    assert p.tools == ["talent_research"]
    assert (p.max_provider_calls_per_run, p.max_fetches_per_run) == (2, 5)
    assert p.status == "active"
    assert len(SP.list_specialists()) == 39
