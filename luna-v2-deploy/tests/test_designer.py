"""Tests for the Designer specialist (theme proposals).

No network anywhere: provider-generated proposals run through an
in-memory fake transport, exactly like the dispatch tests.
"""

import json

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import missions as M
from luna_v2 import designer as DES

OWNER = "jason"

MOONLIGHT = {
    "background": "#121212",
    "surface": "#1E1E1E",
    "text": "#FFFFFF",
    "muted": "#4C5463",
    "accent": "#9C27B0",
    "accent_text": "#FFFFFF",
    "border": "#222222",
    "max_width": 1100,
    "roundness": 18,
}


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    B.seed_providers(s, OWNER)
    yield s
    s.close()


def valid_tokens(**overrides):
    t = dict(MOONLIGHT)
    t.update(overrides)
    return t


def fake_transport_factory(calls, text, usage=None):
    usage = dict(usage or {"requests": 1.0, "tokens": 42.0})

    def fake(provider, prompt):
        calls.append((provider, prompt))
        return text, dict(usage)

    return fake


def usage_rows(s):
    return s._db.execute(
        "SELECT * FROM broker_usage WHERE owner = ?", (OWNER,)).fetchall()


# ---------------------------------------------------------------------------
# WCAG math
# ---------------------------------------------------------------------------
def test_contrast_math_basics():
    assert DES.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(
        21.0, rel=1e-3)
    assert DES.contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    assert DES.relative_luminance("#000000") == pytest.approx(0.0, abs=1e-6)
    assert DES.relative_luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_moonlight_validates():
    assert DES.validate_tokens(dict(MOONLIGHT))["background"] == "#121212"


def test_low_contrast_names_every_failing_pair():
    with pytest.raises(DES.DesignerError) as exc:
        DES.validate_tokens(valid_tokens(text="#777777",
                                         background="#888888"))
    msg = str(exc.value)
    assert "text on background" in msg
    # one error, all failures listed at once
    assert msg.startswith("theme validation failed")


def test_missing_key_is_named():
    tokens = valid_tokens()
    del tokens["accent"]
    with pytest.raises(DES.DesignerError, match="missing color token 'accent'"):
        DES.validate_tokens(tokens)


def test_bad_hex_and_unknown_key_and_numeric_range_all_reported():
    with pytest.raises(DES.DesignerError) as exc:
        DES.validate_tokens(valid_tokens(border="red",
                                         max_width=5000,
                                         sparkle="#FFFFFF"))
    msg = str(exc.value)
    assert "color token 'border'" in msg
    assert "numeric token 'max_width'" in msg
    assert "unknown token 'sparkle'" in msg


# ---------------------------------------------------------------------------
# propose / approve / reject
# ---------------------------------------------------------------------------
def test_propose_stores_proposed_and_lists(store):
    pid = DES.propose(store, OWNER, "Ocean", valid_tokens(),
                      rationale="deep blue calm")
    row = store._db.execute(
        "SELECT * FROM design_proposals WHERE id = ?", (pid,)).fetchone()
    assert row["state"] == "proposed"
    assert row["rationale"] == "deep blue calm"
    assert json.loads(row["tokens_json"])["text"] == "#FFFFFF"
    assert len(DES.list_proposals(store, OWNER)) == 1


def test_propose_rejects_invalid_before_storing(store):
    with pytest.raises(DES.DesignerError):
        DES.propose(store, OWNER, "Fog", valid_tokens(text="#777777",
                                                      background="#888888"))
    assert DES.list_proposals(store, OWNER) == []


def test_approve_stamps_decider(store):
    pid = DES.propose(store, OWNER, "Ocean", valid_tokens())
    DES.approve(store, OWNER, pid, approved_by="jason")
    row = store._db.execute(
        "SELECT * FROM design_proposals WHERE id = ?", (pid,)).fetchone()
    assert row["state"] == "approved"
    assert row["decided_by"] == "jason"
    assert row["decided_at"]
    assert DES.current_theme(store, OWNER) == DES.validate_tokens(
        dict(MOONLIGHT))


def test_approve_twice_raises(store):
    pid = DES.propose(store, OWNER, "Ocean", valid_tokens())
    DES.approve(store, OWNER, pid, approved_by="jason")
    with pytest.raises(DES.ProposalNotProposed, match="only a 'proposed'"):
        DES.approve(store, OWNER, pid, approved_by="jason")


def test_blank_approver_raises_and_stores_nothing_changed(store):
    pid = DES.propose(store, OWNER, "Ocean", valid_tokens())
    with pytest.raises(DES.DesignerError, match="named approver"):
        DES.approve(store, OWNER, pid, approved_by="   ")
    with pytest.raises(DES.DesignerError, match="named decider"):
        DES.reject(store, OWNER, pid, approved_by="")
    row = store._db.execute(
        "SELECT state FROM design_proposals WHERE id = ?", (pid,)).fetchone()
    assert row["state"] == "proposed"


def test_reject_records_state(store):
    pid = DES.propose(store, OWNER, "Fog", valid_tokens())
    DES.reject(store, OWNER, pid, approved_by="jason", reason="too dim")
    row = store._db.execute(
        "SELECT state, decided_by FROM design_proposals WHERE id = ?",
        (pid,)).fetchone()
    assert row["state"] == "rejected"
    assert row["decided_by"] == "jason"


def test_proposals_are_owner_scoped(store):
    pid = DES.propose(store, OWNER, "Ocean", valid_tokens())
    assert DES.list_proposals(store, "guest") == []
    with pytest.raises(DES.ProposalAccessDenied):
        DES.approve(store, "guest", pid, approved_by="guest")


def test_current_theme_none_until_approved(store):
    assert DES.current_theme(store, OWNER) is None
    pid = DES.propose(store, OWNER, "Ocean", valid_tokens())
    assert DES.current_theme(store, OWNER) is None
    DES.approve(store, OWNER, pid, approved_by="jason")
    assert DES.current_theme(store, OWNER)["accent"] == "#9C27B0"


def test_current_theme_is_the_latest_approved(store):
    p1 = DES.propose(store, OWNER, "First", valid_tokens())
    p2 = DES.propose(store, OWNER, "Second", valid_tokens(accent="#00695C"))
    DES.approve(store, OWNER, p1, approved_by="jason")
    DES.approve(store, OWNER, p2, approved_by="jason")
    assert DES.current_theme(store, OWNER)["accent"] == "#00695C"


# ---------------------------------------------------------------------------
# seed_moonlight
# ---------------------------------------------------------------------------
def test_seed_moonlight_is_idempotent(store):
    first = DES.seed_moonlight(store, OWNER)
    assert DES.current_theme(store, OWNER) == DES.validate_tokens(
        dict(MOONLIGHT))
    assert DES.seed_moonlight(store, OWNER) == first
    approved = DES.list_proposals(store, OWNER, state="approved")
    assert len(approved) == 1
    assert approved[0]["name"] == "Moonlight Workspace"
    assert approved[0]["decided_by"] == "jason"


def test_seed_moonlight_leaves_existing_approved_theme_alone(store):
    pid = DES.propose(store, OWNER, "Ocean", valid_tokens(accent="#00695C"))
    DES.approve(store, OWNER, pid, approved_by="jason")
    assert DES.seed_moonlight(store, OWNER) == pid
    assert DES.current_theme(store, OWNER)["accent"] == "#00695C"


# ---------------------------------------------------------------------------
# propose_from_provider
# ---------------------------------------------------------------------------
def test_provider_proposal_parses_fenced_json_and_stores(store):
    mission_id = M.create_mission(store, OWNER, "theme mission",
                                  outcome="").id
    calls = []
    text = ("```json\n"
            + json.dumps({"tokens": MOONLIGHT,
                          "rationale": "calm night ops"}) + "\n```")
    pid = DES.propose_from_provider(
        store, OWNER, "Night Ops", "something for late-night work",
        transport=fake_transport_factory(calls, text), mission_id=mission_id)
    assert len(calls) == 1
    prompt = calls[0][1]
    assert "STRICT JSON ONLY" in prompt
    assert "late-night work" in prompt
    row = store._db.execute(
        "SELECT * FROM design_proposals WHERE id = ?", (pid,)).fetchone()
    assert row["state"] == "proposed"
    assert row["rationale"] == "calm night ops"
    assert json.loads(row["tokens_json"])["background"] == "#121212"
    # the call really happened and is broker-accounted, mission-attributed
    rows = usage_rows(store)
    assert len(rows) == 2  # requests + tokens
    assert all(r["mission_id"] == mission_id for r in rows)


def test_provider_proposal_refuses_without_transport(store):
    with pytest.raises(DES.DesignerError, match="needs a transport"):
        DES.propose_from_provider(store, OWNER, "Night Ops",
                                  "a calm night theme", transport=None)
    assert DES.list_proposals(store, OWNER) == []
    assert usage_rows(store) == []


def test_garbage_output_raises_and_stores_nothing_but_usage_stands(store):
    calls = []
    with pytest.raises(DES.DesignerError, match="no JSON object"):
        DES.propose_from_provider(
            store, OWNER, "Noise", "a theme",
            transport=fake_transport_factory(calls, "beige is nice"))
    assert DES.list_proposals(store, OWNER) == []
    # the spend was real: dispatch recorded usage, the proposal was not
    rows = usage_rows(store)
    assert len(rows) == 2


def test_failing_palette_from_provider_stores_nothing(store):
    calls = []
    text = json.dumps({"tokens": valid_tokens(text="#777777",
                                              background="#888888"),
                       "rationale": "foggy"})
    with pytest.raises(DES.DesignerError, match="text on background"):
        DES.propose_from_provider(store, OWNER, "Fog", "a foggy theme",
                                  transport=fake_transport_factory(calls,
                                                                   text))
    assert DES.list_proposals(store, OWNER) == []


def test_non_json_object_output_raises(store):
    calls = []
    with pytest.raises(DES.DesignerError, match="JSON object"):
        DES.propose_from_provider(store, OWNER, "Array", "a theme",
                                  transport=fake_transport_factory(
                                      calls, "[1, 2, 3]"))
    assert DES.list_proposals(store, OWNER) == []
