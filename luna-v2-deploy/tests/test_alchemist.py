"""Tests for the Alchemist — the experiment lab.

Jason's lab law: experiments run on scratch copies, sandboxes, the
island — never on the living system. These tests pin the refusals,
the copy isolation, the broker accounting, and the verdict
discipline (only Jason or Rowan decides).
"""

import hashlib

import pytest

from luna_v2.store import Store
from luna_v2 import alchemist as AL
from luna_v2 import broker as B
from luna_v2 import conductor as CO

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "lab.db"))
    yield s
    s.close()


def exp_count(s):
    AL._ensure_schema(s)
    return s._db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fake(calls, text="lab result", fail_on=None):
    """Stub transport: records (provider, prompt), returns canned text."""
    def fake_transport(provider, prompt):
        calls.append((provider, prompt))
        if fail_on is not None and fail_on in prompt:
            raise RuntimeError("provider exploded on purpose")
        return text, {"requests": 1.0, "tokens": 42.0}
    return fake_transport


# --- Jason's lab law: nothing live-shaped is ever proposed -------------

@pytest.mark.parametrize("params", [
    {"target": "live"},
    {"target": "LIVE database"},
    {"target": "throne"},
    {"target": "THRONE"},
    {"target": "production"},
    {"target": "Production-db"},
    {"db": "throne"},
    {"path": "/live/missions"},
    {"DB": "my live db"},
])
def test_live_shaped_proposals_refused(store, params):
    with pytest.raises(AL.ExperimentRefused, match="living system"):
        AL.propose(store, OWNER, "sneaky lab", "what if we try it live",
                   "tabletop", params=params)
    assert exp_count(store) == 0  # refusals write nothing


def test_clean_tabletop_proposes(store):
    r = AL.propose(store, OWNER, "Lab 1", "a scratch copy is enough",
                   "tabletop", params={"simulate": "conductor_tick",
                                       "target": "scratch-copy"})
    assert r["status"] == "proposed"
    assert r["budget_calls"] == 0


def test_blank_hypothesis_and_title_refused(store):
    with pytest.raises(AL.ExperimentRefused):
        AL.propose(store, OWNER, "title ok", "   ", "tabletop")
    with pytest.raises(AL.ExperimentRefused):
        AL.propose(store, OWNER, "   ", "hypothesis ok", "tabletop")
    with pytest.raises(AL.ExperimentRefused):
        AL.propose(store, OWNER, "t", "h", "warp_drive")
    assert exp_count(store) == 0


def test_dispatch_ab_needs_two_budgeted_calls(store):
    with pytest.raises(AL.ExperimentRefused, match="budget_calls >= 2"):
        AL.propose(store, OWNER, "AB lab", "which prompt wins",
                   "dispatch_ab",
                   params={"question": "q", "prompt_a": "a", "prompt_b": "b"},
                   budget_calls=1)
    assert exp_count(store) == 0


# --- Tabletop: copy isolation ------------------------------------------

def test_tabletop_conductor_tick_runs_on_a_copy(store):
    CO.add_backlog(store, OWNER, "Lab training drill", "training")
    r = AL.propose(store, OWNER, "Lab 1", "a dry run previews the tick",
                   "tabletop", params={"simulate": "conductor_tick"})
    live = store.path
    done = AL.run_experiment(store, OWNER, r["id"])
    assert done["status"] == "done"
    # the runner's own isolation check: the live file was hashed before
    # and after the SIMULATION work on the copy and matched — the tick
    # executed against the throwaway twin only
    assert "live DB untouched: sha256 matched before/after" in done["result"]
    assert "isolated DB copy" in done["result"]
    assert "would assign 1 item(s):" in done["result"]
    assert "Lab training drill" in done["result"]
    # ...and the live backlog/mission books still show the original state
    assert store._db.execute(
        "SELECT status FROM work_backlog WHERE owner = ?",
        (OWNER,)).fetchone()["status"] == "open"
    assert store._db.execute(
        "SELECT COUNT(*) FROM missions WHERE owner = ?",
        (OWNER,)).fetchone()[0] == 0


def test_tabletop_unknown_simulation_is_honest(store):
    r = AL.propose(store, OWNER, "Lab X", "unknown sims fail loudly",
                   "tabletop", params={"simulate": "flux_capacitor"})
    done = AL.run_experiment(store, OWNER, r["id"])
    assert done["status"] == "done"
    assert "unknown tabletop simulation 'flux_capacitor'" in done["result"]


def test_only_proposed_experiments_run(store):
    r = AL.propose(store, OWNER, "Lab 1", "runs once",
                   "tabletop", params={"simulate": "conductor_tick"})
    AL.run_experiment(store, OWNER, r["id"])
    with pytest.raises(AL.ExperimentRefused, match="only proposed"):
        AL.run_experiment(store, OWNER, r["id"])
    with pytest.raises(AL.ExperimentNotFound):
        AL.run_experiment(store, OWNER, 4242)


# --- dispatch_ab: broker-routed, honestly recorded -----------------------

@pytest.fixture()
def brokered(tmp_path):
    s = Store(str(tmp_path / "ab.db"))
    B.seed_providers(s, OWNER)
    yield s
    s.close()


def _ab_params():
    return {"question": "which label is better?",
            "prompt_a": "Answer: variant A",
            "prompt_b": "Answer: variant B"}


def test_dispatch_ab_records_two_outputs_and_usage(brokered):
    calls = []
    r = AL.propose(brokered, OWNER, "AB 1", "A vs B, measured",
                   "dispatch_ab", params=_ab_params(), budget_calls=2)
    done = AL.run_experiment(brokered, OWNER, r["id"],
                             transport=fake(calls))
    assert done["status"] == "done"
    assert len(calls) == 2
    assert calls[0][1] == "Answer: variant A"
    assert calls[1][1] == "Answer: variant B"
    assert "lab result" in done["result"]
    assert "A:" in done["result"] and "B:" in done["result"]
    # both dispatches went through the broker's ledger
    usage = brokered._db.execute(
        "SELECT COUNT(*) FROM broker_usage WHERE owner = ?",
        (OWNER,)).fetchone()[0]
    assert usage == 4  # 2 dispatches x 2 units
    ledger = brokered.list_ledger(OWNER)
    assert len(ledger) == 4
    assert all(e["cost_avoided"] == 0.0 for e in ledger)


def test_dispatch_ab_truncates_long_outputs(brokered):
    calls = []
    r = AL.propose(brokered, OWNER, "AB long", "truncation holds",
                   "dispatch_ab", params=_ab_params(), budget_calls=2)
    done = AL.run_experiment(
        brokered, OWNER, r["id"],
        transport=fake(calls, text="x" * 600))
    assert "…(truncated)" in done["result"]
    assert "x" * 600 not in done["result"]


def test_dispatch_ab_failure_recorded_not_fabricated(brokered):
    calls = []
    r = AL.propose(brokered, OWNER, "AB fail", "failure is a result too",
                   "dispatch_ab", params=_ab_params(), budget_calls=2)
    done = AL.run_experiment(
        brokered, OWNER, r["id"],
        transport=fake(calls, fail_on="variant B"))
    assert done["status"] == "done"
    assert "FAILED" in done["result"]
    assert "nothing fabricated" in done["result"]
    # the failure is attributed to the B side only
    a_side, b_side = done["result"].split("B:")
    assert "FAILED" not in a_side
    assert "FAILED" in b_side


def test_dispatch_ab_refuses_blank_prompts(brokered):
    r = AL.propose(brokered, OWNER, "AB blank", "blanks refuse at run",
                   "dispatch_ab",
                   params={"question": "q", "prompt_a": "a", "prompt_b": " "},
                   budget_calls=2)
    done = AL.run_experiment(brokered, OWNER, r["id"],
                             transport=fake([]))
    assert done["status"] == "done"
    assert "refused at run time" in done["result"]


# --- Verdicts: humans decide --------------------------------------------

def test_verdict_discipline(store):
    r = AL.propose(store, OWNER, "Lab 1", "verdict flow",
                   "tabletop", params={"simulate": "conductor_tick"})
    AL.run_experiment(store, OWNER, r["id"])
    with pytest.raises(AL.VerdictRefused, match="decider"):
        AL.verdict(store, OWNER, r["id"], "adopt", "")
    with pytest.raises(AL.VerdictRefused, match="cannot decide"):
        AL.verdict(store, OWNER, r["id"], "adopt", "alchemist")
    with pytest.raises(AL.VerdictRefused, match="cannot decide"):
        AL.verdict(store, OWNER, r["id"], "adopt", " Alchemist ")
    done = AL.verdict(store, OWNER, r["id"], "kill", "jason")
    assert done["status"] == "killed"
    assert done["verdict"] == "kill"
    assert done["verdict_by"] == "jason"


def test_verdict_on_proposed_experiment_refused(store):
    r = AL.propose(store, OWNER, "Lab 1", "not run yet",
                   "tabletop", params={"simulate": "conductor_tick"})
    with pytest.raises(AL.VerdictRefused, match="only recorded on done"):
        AL.verdict(store, OWNER, r["id"], "adopt", "rowan")


def test_notebook_newest_first(store):
    first = AL.propose(store, OWNER, "Lab 1", "first", "tabletop",
                       params={"simulate": "conductor_tick"})
    second = AL.propose(store, OWNER, "Lab 2", "second", "tabletop",
                        params={"simulate": "conductor_tick"})
    rows = AL.notebook(store, OWNER)
    assert [r["id"] for r in rows] == [second["id"], first["id"]]


def test_params_accept_json_string(store):
    r = AL.propose(store, OWNER, "Lab json", "json params work",
                   "tabletop", params='{"simulate": "conductor_tick"}')
    assert r["kind"] == "tabletop"
    with pytest.raises(AL.ExperimentRefused):
        AL.propose(store, OWNER, "Lab json", "bad json", "tabletop",
                   params='{"simulate":')
