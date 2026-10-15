"""Tests for Independent Minds (luna_v2/minds.py).

Jason's ruling (2026-10-14): "i need all agents to be their own
independent thinkers, not you in a new hat." A consult is one
specialist thinking once, in his own voice: the prompt is assembled
from HIS registry profile, HIS written charter, the task, and his
own real records; the words come back from ONE broker-accounted
dispatch and are recorded verbatim in mind_outputs — the audit
trail. These tests pin the discipline: budget checked before
spending (a zero-budget specialist refuses with nothing recorded),
unknown/planned/retired minds refuse cleanly, a failed dispatch
records no output, and minds.py itself touches no network — the
only way words are made is the existing dispatch path.
"""

import ast
import inspect
import json

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import dispatch as D
from luna_v2 import minds
from luna_v2 import specialists as SP

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "minds.db"))
    B.seed_providers(s, OWNER)
    yield s
    s.close()


def fake_transport_factory(calls, text="his exact words", usage=None):
    usage = dict(usage or {"requests": 1.0, "tokens": 321.0})

    def fake(provider, prompt):
        calls.append((provider, prompt))
        return text, dict(usage)

    return fake


def _counts(store):
    minds._ensure_schema(store)
    SP._ensure_schema(store)
    out = store._db.execute(
        "SELECT COUNT(*) FROM mind_outputs").fetchone()[0]
    runs = store._db.execute(
        "SELECT COUNT(*) FROM specialist_runs").fetchone()[0]
    used = store._db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM broker_usage").fetchone()[0]
    return out, runs, used


# ---------------------------------------------------------------------------
# Prompt assembly: his profile, his charter, the task, his records
# ---------------------------------------------------------------------------
def test_prompt_carries_charter_task_and_context(store):
    calls = []
    r = minds.consult(
        store, "lantern", "Review your campaign.",
        "GAP-RECORD-MARKER: no chat UI anywhere",
        transport=fake_transport_factory(calls))
    assert len(calls) == 1
    prompt = calls[0][1]
    # his registry identity
    assert "lantern" in prompt and "The Guiding Light" in prompt
    # his charter, with Jason's limits in it
    charter = minds.CHARTERS["lantern"]
    assert charter in prompt
    assert "never approve a consequential" in prompt
    assert "Jason alone approves" in prompt
    assert "never certify your own stages" in prompt
    # the task and his records, unaltered
    assert "Review your campaign." in prompt
    assert "GAP-RECORD-MARKER: no chat UI anywhere" in prompt
    assert r.specialist == "lantern"


def test_default_charter_for_unchartered_specialist(store):
    # A specialist with dispatch budget but no authored charter gets
    # the standing default, built from his own profile — never a
    # borrowed personality.
    calls = []
    minds.consult(store, "scout", "Think about the route.",
                  "some records",
                  transport=fake_transport_factory(calls))
    prompt = calls[0][1]
    assert "Research Scout" in prompt
    assert "never invent" in prompt
    assert minds.CHARTERS.get("scout") is None


# ---------------------------------------------------------------------------
# The audit trail: output recorded verbatim, attributed, accounted
# ---------------------------------------------------------------------------
def test_output_recorded_with_attribution_and_usage(store):
    calls = []
    words = "First line is mine.\nSecond line too — unedited."
    r = minds.consult(
        store, "lantern", "task one", "context one",
        transport=fake_transport_factory(
            calls, text=words, usage={"requests": 1.0, "tokens": 999.0}))
    assert r.output_text == words
    rows = minds.list_outputs(store, OWNER, "lantern")
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == r.output_id
    assert row["output_text"] == words  # byte-for-byte, no caller edits
    assert row["task"] == "task one"
    assert row["run_id"] == r.run_id
    assert json.loads(row["usage_json"]) == {"requests": 1.0,
                                             "tokens": 999.0}
    assert row["provider"] == "groq" and row["model"]
    # the shared run ledger carries the same words as the run result
    run = SP.get_run(store, r.run_id)
    assert run["status"] == "done" and run["result"] == words
    assert run["specialist"] == "lantern"
    # and the broker accounted the spend: usage rows + ledger exist
    assert r.usage_ids and r.ledger_ids
    _, _, used_tokens = _counts(store)
    # tokens sum over both units' rows is not meaningful; check the
    # tokens unit directly through the broker's own books
    start, end = B._period_bounds("daily", B._now())
    assert store.usage_sum(OWNER, "groq", "tokens", start, end) == 999.0


def test_mission_attribution_flows_through(store):
    from luna_v2 import missions as M
    m = M.create_mission(store, OWNER, "thinking mission", "outcome")
    calls = []
    r = minds.consult(store, "lantern", "task", "ctx",
                      transport=fake_transport_factory(calls),
                      mission_id=m.id)
    row = minds.list_outputs(store, OWNER, "lantern")[0]
    assert row["mission_id"] == m.id
    run = SP.get_run(store, r.run_id)
    assert run["mission_id"] == m.id


# ---------------------------------------------------------------------------
# Refusals: clean, early, and with zero side effects
# ---------------------------------------------------------------------------
def test_budget_refusal_spends_nothing_and_records_nothing(store):
    # Tallyman's registry budget is ZERO provider calls — a consult
    # is one call, so the budget law refuses it before anything is
    # spent or written.
    assert SP.SPECIALISTS["tallyman"].max_provider_calls_per_run == 0
    calls = []
    with pytest.raises(SP.BudgetExceeded):
        minds.consult(store, "tallyman", "think about efficiency",
                      "the burn records",
                      transport=fake_transport_factory(calls))
    assert calls == []  # transport never invoked
    assert _counts(store) == (0, 0, 0)


def test_unknown_specialist_refused(store):
    calls = []
    with pytest.raises(SP.SpecialistNotFound):
        minds.consult(store, "nobody", "task", "ctx",
                      transport=fake_transport_factory(calls))
    assert calls == []
    assert _counts(store) == (0, 0, 0)


def test_planned_specialist_refused(store, monkeypatch):
    ghost = SP.SpecialistProfile(
        name="ghost", title="Ghost", purpose="not yet real",
        tools=["provider_dispatch"], max_provider_calls_per_run=1,
        max_fetches_per_run=0, status="planned")
    monkeypatch.setitem(SP.SPECIALISTS, "ghost", ghost)
    calls = []
    with pytest.raises(SP.SpecialistNotActive):
        minds.consult(store, "ghost", "task", "ctx",
                      transport=fake_transport_factory(calls))
    assert calls == []
    assert _counts(store) == (0, 0, 0)


def test_retired_specialist_refused(store):
    SP.set_specialist_status(store, OWNER, "lantern", "retired",
                             "jason", note="test retirement")
    calls = []
    with pytest.raises(SP.SpecialistNotActive):
        minds.consult(store, "lantern", "task", "ctx",
                      transport=fake_transport_factory(calls))
    assert calls == []
    outs, runs, used = _counts(store)
    assert outs == 0 and used == 0
    assert runs == 0


def test_blank_task_and_missing_transport_refused(store):
    calls = []
    with pytest.raises(minds.MindsError):
        minds.consult(store, "lantern", "   ", "ctx",
                      transport=fake_transport_factory(calls))
    with pytest.raises(minds.MindsError):
        minds.consult(store, "lantern", "task", "ctx", transport=None)
    assert calls == []
    assert _counts(store) == (0, 0, 0)


def test_failed_dispatch_records_no_output(store):
    def boom(provider, prompt):
        raise D.DispatchError("provider is down")

    with pytest.raises(D.DispatchError):
        minds.consult(store, "lantern", "task", "ctx", transport=boom)
    outs, runs, used = _counts(store)
    assert outs == 0 and used == 0
    assert runs == 1  # the attempt is on the run ledger, marked failed
    run = store._db.execute(
        "SELECT * FROM specialist_runs").fetchone()
    assert run["status"] == "failed"
    assert "provider is down" in run["error"]


# ---------------------------------------------------------------------------
# Structural: minds makes words only through the existing dispatch
# ---------------------------------------------------------------------------
def test_minds_imports_no_network_directly():
    tree = ast.parse(inspect.getsource(minds))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    banned = {"urllib", "http", "socket", "requests", "subprocess"}
    assert not (imported & banned), imported
    assert "luna_v2" in imported  # words only via luna_v2.dispatch
