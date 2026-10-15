"""Tests for Lantern (luna_v2/lantern.py) — the prime specialist.

Jason's charter (2026-10-14): one standing task — make Luna/ORBIT
competitive with best-in-class companion apps (benchmark: Tolan) —
executed as a staged campaign, delegated through the court, with
priority in line. These tests pin the discipline: stages need a
written definition of done, gaps need a source, delegations go only
to registered specialists, and Lantern can NEVER certify his own
stage — completion demands evidence plus a verifier who is not him.
"""

import pytest

from luna_v2.store import Store
from luna_v2 import lantern as LA
from luna_v2 import specialists as SP
from luna_v2 import web

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "lantern.db"))
    yield s
    s.close()


def _stage(store, name="Chat-first app", seq=1):
    return LA.add_stage(store, OWNER, name,
                        benchmark_target="Tolan's chat home",
                        definition_of_done="one sentence becomes a "
                                           "mission from the browser",
                        seq=seq)


# ---------------------------------------------------------------------------
# Registry / face
# ---------------------------------------------------------------------------
def test_profile_is_prime_and_thinks_on_a_budget():
    # Jason's independent-minds ruling (2026-10-14) supersedes the
    # hiring-era "zero provider calls" line: Lantern now thinks in
    # his own voice — exactly ONE broker-accounted dispatch per
    # consult, never more, and still zero fetches.
    p = SP.SPECIALISTS["lantern"]
    assert p.title == "The Guiding Light"
    assert p.status == "active"
    assert p.tools == ["campaign_ledger", "provider_dispatch"]
    assert p.max_provider_calls_per_run == 1
    assert p.max_fetches_per_run == 0


def test_team_art_face():
    art = web.TEAM_ART["lantern"]
    assert art["emoji"] == "🏮"
    assert art["color"] == "#00E676"
    assert art["flavor"]


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def test_stage_needs_definition_of_done(store):
    with pytest.raises(LA.LanternError):
        LA.add_stage(store, OWNER, "Vague stage",
                     definition_of_done="  ")


def test_stage_add_is_idempotent(store):
    a = _stage(store)
    b = _stage(store)
    assert a["id"] == b["id"]
    assert len(LA.list_stages(store, OWNER)) == 1
    assert a["status"] == "planned"


def test_stage_moves_and_done_is_refused_via_status(store):
    s = _stage(store)
    assert LA.set_stage_status(store, OWNER, s["id"], "active")["status"] \
        == "active"
    with pytest.raises(LA.LanternError):
        LA.set_stage_status(store, OWNER, s["id"], "done")
    with pytest.raises(LA.LanternError):
        LA.set_stage_status(store, OWNER, s["id"], "planned-x")


def test_complete_stage_requires_evidence_and_outside_verifier(store):
    s = _stage(store)
    with pytest.raises(LA.LanternError):
        LA.complete_stage(store, OWNER, s["id"], "", "verifier")
    with pytest.raises(LA.LanternError):
        LA.complete_stage(store, OWNER, s["id"], "proof", "")
    with pytest.raises(LA.LanternError):
        LA.complete_stage(store, OWNER, s["id"], "proof", "lantern")
    with pytest.raises(LA.LanternError):
        LA.complete_stage(store, OWNER, s["id"], "proof", "Lantern")
    done = LA.complete_stage(store, OWNER, s["id"],
                             "736 tests green; inbox live",
                             "verifier")
    assert done["status"] == "done"
    assert done["verified_by"] == "verifier"
    with pytest.raises(LA.LanternError):
        LA.complete_stage(store, OWNER, s["id"], "again", "verifier")


# ---------------------------------------------------------------------------
# Gaps
# ---------------------------------------------------------------------------
def test_gap_needs_source_and_severity_is_checked(store):
    with pytest.raises(LA.LanternError):
        LA.add_gap(store, OWNER, "no source gap", "")
    with pytest.raises(LA.LanternError):
        LA.add_gap(store, OWNER, "bad sev", "inventory",
                   severity="enormous")
    g = LA.add_gap(store, OWNER, "No chat UI", "Luna-App-Inventory §3",
                   severity="critical")
    assert g["status"] == "open"
    again = LA.add_gap(store, OWNER, "No chat UI", "Luna-App-Inventory §3")
    assert again["id"] == g["id"]  # idempotent re-statement
    assert LA.set_gap_status(store, OWNER, g["id"], "addressed")["status"] \
        == "addressed"
    assert LA.list_gaps(store, OWNER, "open") == []


def test_gap_stage_link_must_exist(store):
    with pytest.raises(LA.LanternError):
        LA.add_gap(store, OWNER, "orphan gap", "inventory", stage_id=99)
    s = _stage(store)
    g = LA.add_gap(store, OWNER, "linked gap", "inventory",
                   stage_id=s["id"])
    assert g["stage_id"] == s["id"]


# ---------------------------------------------------------------------------
# Delegations
# ---------------------------------------------------------------------------
def test_delegate_only_to_registered_specialists(store):
    with pytest.raises(LA.LanternError):
        LA.delegate(store, OWNER, "nobody", "do the thing")
    with pytest.raises(LA.LanternError):
        LA.delegate(store, OWNER, "builder", "  ")
    d = LA.delegate(store, OWNER, "builder", "build the chat home")
    assert d["status"] == "assigned"
    assert LA.set_delegation_status(
        store, OWNER, d["id"], "in_progress")["status"] == "in_progress"
    assert len(LA.list_delegations(store, OWNER, "in_progress")) == 1


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def test_campaign_report_is_deterministic_and_honest(store):
    s1 = _stage(store)
    LA.set_stage_status(store, OWNER, s1["id"], "active")
    s2 = LA.add_stage(store, OWNER, "Phone reach", seq=2,
                      benchmark_target="Tolan on the phone",
                      definition_of_done="HELM reaches Luna")
    LA.set_stage_status(store, OWNER, s2["id"], "blocked",
                        note="waiting on Jason's Tailscale step")
    LA.add_gap(store, OWNER, "No chat UI", "inventory", severity="critical",
               stage_id=s1["id"])
    LA.add_gap(store, OWNER, "No voice", "research", severity="info")
    LA.delegate(store, OWNER, "stepwriter", "wire Stepwriter into the "
                                            "browser", stage_id=s1["id"])
    r1 = LA.campaign_report(store, OWNER)
    r2 = LA.campaign_report(store, OWNER)
    assert r1 == r2
    assert "LANTERN CAMPAIGN" in r1
    assert "[active] Chat-first app" in r1
    assert "Open gaps: 2 (critical 1, warning 0, info 1)" in r1
    assert "No chat UI" in r1 and "stage: Chat-first app" in r1
    assert "stepwriter" in r1
    assert "Blocked stages" in r1 and "Tailscale" in r1


def test_campaign_report_empty(store):
    r = LA.campaign_report(store, OWNER)
    assert "No campaign stages laid out yet." in r
    assert "Open gaps: none recorded." in r
    assert "Blocked on Jason: nothing right now." in r


# ---------------------------------------------------------------------------
# His own thinking (minds.consult — Jason's independent-minds ruling)
# ---------------------------------------------------------------------------
from luna_v2 import broker as B
from luna_v2 import minds


def _fake_transport_factory(calls, text="lantern's own words",
                            usage=None):
    usage = dict(usage or {"requests": 1.0, "tokens": 50.0})

    def fake(provider, prompt):
        calls.append((provider, prompt))
        return text, dict(usage)

    return fake


def test_think_returns_his_exact_words_and_files_nothing(store):
    s1 = _stage(store)
    LA.set_stage_status(store, OWNER, s1["id"], "active")
    LA.add_gap(store, OWNER, "No chat UI", "inventory",
               severity="critical", stage_id=s1["id"])
    LA.delegate(store, OWNER, "stepwriter",
                 "wire Stepwriter into the browser", stage_id=s1["id"])
    B.seed_providers(store, OWNER)
    calls = []
    words = "Ship the chat-first home next.\nThat is my call."
    r = LA.think(store, OWNER,
                 transport=_fake_transport_factory(calls, text=words))
    # his words come back byte-for-byte — nobody edited them
    assert r.output_text == words
    assert len(calls) == 1  # one consult, one dispatch
    # the prompt carried his real records, not a summary of them
    prompt = calls[0][1]
    assert "No chat UI" in prompt and "Chat-first app" in prompt
    assert LA.THINK_TASK.split(".")[0] in prompt
    # the audit trail holds the same words, attributed to him
    rows = minds.list_outputs(store, OWNER, "lantern")
    assert len(rows) == 1
    assert rows[0]["output_text"] == words
    assert rows[0]["run_id"] == r.run_id
    # and NOTHING was filed: the ledger is exactly as he found it
    assert len(LA.list_stages(store, OWNER)) == 1
    assert len(LA.list_gaps(store, OWNER)) == 1
    assert len(LA.list_delegations(store, OWNER)) == 1
    assert LA.list_stages(store, OWNER)[0]["status"] == "active"
    assert LA.list_gaps(store, OWNER)[0]["status"] == "open"


def test_think_path_cannot_mutate_the_ledger():
    # Structural: the functions that make up the think path may read
    # the campaign (campaign_report) and consult the mind — they may
    # never call a stage/gap/delegation mutation.
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(LA))
    mutations = {"add_stage", "set_stage_status", "complete_stage",
                 "add_gap", "set_gap_status", "delegate",
                 "set_delegation_status"}
    think_fns = {"think"}
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in think_fns:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    f = sub.func
                    called = (f.attr if isinstance(f, ast.Attribute)
                              else getattr(f, "id", ""))
                    assert called not in mutations, (
                        f"think path calls ledger mutation {called}")
                    seen.add(called)
    assert "consult" in seen  # the path really goes through minds
