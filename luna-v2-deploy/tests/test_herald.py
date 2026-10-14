"""Tests for the Herald: Jason's four-part briefings.

Every stamp is backed by a real check — the tests verify the stamp
text matches an actual Verifier run, not a claim. The mission test
runs the full honest lifecycle (create, plan, complete with evidence,
close) through the real mission APIs.
"""

import os
import tempfile

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import herald as H
from luna_v2 import rewards as RW

OWNER = "jason"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _closed_mission(s, title="Test mission"):
    m = M.create_mission(s, OWNER, title)
    s1 = M.add_step(s, OWNER, m.id, "First step", kind="routine")
    s2 = M.add_step(s, OWNER, m.id, "Second step", kind="routine")
    M.complete_step(s, s1.id, "it worked", evidence="log line 1")
    M.complete_step(s, s2.id, "also worked", evidence="log line 2")
    M.close_mission(s, m.id)
    return m.id


# ---------------------------------------------------------------------------
# Mission briefings
# ---------------------------------------------------------------------------
def test_mission_briefing_four_parts(store):
    mid = _closed_mission(store)
    receipt = store.get_receipt(mid)
    b = H.compose_mission_briefing(store, OWNER, mid)
    assert b["kind"] == "mission" and b["ref"] == str(mid)
    # short: title, outcome, receipt, steps, resources
    assert "Test mission" in b["short_text"]
    assert str(receipt["id"]) in b["short_text"]
    assert "2 done of 2" in b["short_text"]
    assert len(b["short_text"].splitlines()) <= 6
    # flow: steps in order, marked done
    first = b["flow_text"].index("First step")
    second = b["flow_text"].index("Second step")
    assert first < second
    assert b["flow_text"].count("\u2713") == 2
    # notes carry real counts
    assert "2 evidence entries" in b["notes"]
    assert "2 step details" in b["notes"]
    # stamp is a REAL verifier outcome, not a claim
    assert "VERIFIED: pass" in b["stamp"]
    # persisted
    rows = H.list_briefings(store, OWNER, kind="mission")
    assert len(rows) == 1 and rows[0]["id"] == b["id"]


def test_mission_briefing_unknown_mission_refused(store):
    with pytest.raises(M.LunaError):
        H.compose_mission_briefing(store, OWNER, 9999)


def test_mission_briefing_no_receipt_open_mission(store):
    m = M.create_mission(store, OWNER, "Still open")
    mid = m.id
    M.add_step(store, OWNER, mid, "A pending step", kind="routine")
    b = H.compose_mission_briefing(store, OWNER, mid)
    assert "no receipt" in b["short_text"]
    assert "\u00b7" in b["flow_text"]  # the pending mark
    assert "VERIFIED: pass" in b["stamp"]


# ---------------------------------------------------------------------------
# Storm briefings
# ---------------------------------------------------------------------------
def test_storm_briefing_fresh_db(store):
    b = H.compose_storm_briefing(store, OWNER)
    assert b["kind"] == "storm"
    assert "mode normal" in b["short_text"]
    assert "Home point: not set" in b["short_text"]
    # stamp is the real watchman verdict
    assert b["stamp"].startswith("WATCHMAN: healthy")


# ---------------------------------------------------------------------------
# Rewards briefings
# ---------------------------------------------------------------------------
def _grant_rows(s, mid):
    RW.grant(s, OWNER, "scout", "cosmetic", 1, "mission", mid,
             granted_by="mentor", note="Scout-Star Hat")
    RW.grant(s, OWNER, "builder", "resource", 5, "mission", mid,
             granted_by="mentor", note="points")
    RW.request_golden_ticket(s, OWNER, "designer",
                             "jump the queue", "mission", mid)


def test_rewards_briefing_counts_and_stamp(store):
    mid = _closed_mission(store)
    _grant_rows(store, mid)
    b = H.compose_rewards_briefing(store, OWNER)
    assert "2 grant(s)" in b["short_text"]
    assert "cosmetic 1" in b["short_text"]
    assert "resource 1" in b["short_text"]
    assert "Golden tickets pending: 1 (designer)" in b["short_text"]
    # the cross-check really ran clean over these rows
    assert b["stamp"].startswith("CROSS-CHECK: clean")
    assert "2 ledger rows" in b["stamp"]
    assert "2 grant rows" in b["notes"]


def test_rewards_briefing_empty_ledger(store):
    b = H.compose_rewards_briefing(store, OWNER)
    assert "0 grant(s)" in b["short_text"]
    assert "CROSS-CHECK: clean (0 ledger rows)" in b["stamp"]
