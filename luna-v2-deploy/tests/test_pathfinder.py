"""Tests for the Pathfinder specialist (luna_v2/pathfinder.py).

The honest v1 boundary is the thing under test: Pathfinder plans and
fetches, but never interacts. An 'interact' step becomes an Envoy
package for Rowan, never an executed click. Off-allowlist fetches are
refused before any network, and secret-shaped page text is redacted
instead of stored.
"""

from luna_v2 import envoy as E
from luna_v2 import pathfinder as PF
from luna_v2 import specialists as SP
from luna_v2.store import Store

import pytest

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _plan(store, goal="read the docs", hosts=("example.com",)):
    return PF.propose_plan(store, OWNER, goal, list(hosts))


def _fake_fetch(mapping):
    def fetch(url):
        if url not in mapping:
            raise SP.FetchFailure(f"{url}: 404 in the test fixture")
        return mapping[url]
    return fetch


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------
def test_plan_needs_goal_and_allowlist(store):
    with pytest.raises(PF.PathfinderError):
        PF.propose_plan(store, OWNER, "   ", ["example.com"])
    with pytest.raises(PF.PathfinderError):
        PF.propose_plan(store, OWNER, "read things", [])
    row = _plan(store)
    assert row["status"] == "planned"
    assert "example.com" in row["allowed_hosts"]


def test_add_step_validates_kind_and_target(store):
    plan = _plan(store)
    with pytest.raises(PF.PathfinderError):
        PF.add_step(store, OWNER, plan["id"], "click", "http://example.com/")
    with pytest.raises(PF.PathfinderError):
        PF.add_step(store, OWNER, plan["id"], "fetch", "   ")
    with pytest.raises(PF.PlanNotFound):
        PF.add_step(store, OWNER, 4242, "fetch", "http://example.com/")
    step = PF.add_step(store, OWNER, plan["id"], "fetch",
                       "http://example.com/page")
    assert step["status"] == "planned"


# ---------------------------------------------------------------------------
# Execution: the read-only half
# ---------------------------------------------------------------------------
def test_fetch_executes_and_stores_text(store):
    plan = _plan(store)
    step = PF.add_step(store, OWNER, plan["id"], "fetch",
                       "http://example.com/page")
    done = PF.execute_step(store, OWNER, step["id"],
                           fetcher=_fake_fetch(
                               {"http://example.com/page": "hello world"}))
    assert done["status"] == "done"
    assert done["evidence"] == "hello world"


def test_off_allowlist_fetch_is_refused_before_network(store):
    plan = _plan(store, hosts=("example.com",))
    step = PF.add_step(store, OWNER, plan["id"], "fetch",
                       "http://evil.example/page")
    calls = []

    def watching(url):
        calls.append(url)
        return "should never be called"

    with pytest.raises(PF.StepRefused):
        PF.execute_step(store, OWNER, step["id"], fetcher=watching)
    assert calls == []  # refused before any network
    again = PF.plan_steps(store, OWNER, plan["id"])[0]
    assert again["status"] == "refused"


def test_secret_shaped_text_is_redacted_not_stored(store):
    plan = _plan(store)
    step = PF.add_step(store, OWNER, plan["id"], "extract",
                       "http://example.com/leak")
    leaked = "api docs. contact: gsk_" + "a" * 24 + " for support."
    done = PF.execute_step(store, OWNER, step["id"],
                           fetcher=_fake_fetch(
                               {"http://example.com/leak": leaked}))
    assert done["status"] == "done"
    assert "[redacted: groq_key" in done["evidence"]
    assert "gsk_" not in done["evidence"]


def test_fetch_budget_refuses_before_spend(store):
    plan = _plan(store)
    fetch = _fake_fetch({f"http://example.com/p{i}": f"page {i}"
                         for i in range(6)})
    cap = SP.get_profile("pathfinder").max_fetches_per_run
    assert cap == 5
    for i in range(5):
        step = PF.add_step(store, OWNER, plan["id"], "fetch",
                           f"http://example.com/p{i}")
        PF.execute_step(store, OWNER, step["id"], fetcher=fetch)
    last = PF.add_step(store, OWNER, plan["id"], "fetch",
                       "http://example.com/p5")
    with pytest.raises(PF.StepRefused):
        PF.execute_step(store, OWNER, last["id"], fetcher=fetch)


def test_only_planned_steps_execute(store):
    plan = _plan(store)
    step = PF.add_step(store, OWNER, plan["id"], "fetch",
                       "http://example.com/page")
    PF.execute_step(store, OWNER, step["id"],
                    fetcher=_fake_fetch(
                        {"http://example.com/page": "x"}))
    with pytest.raises(PF.StepRefused):
        PF.execute_step(store, OWNER, step["id"],
                        fetcher=_fake_fetch({}))
    with pytest.raises(PF.StepNotFound):
        PF.execute_step(store, OWNER, 4242, fetcher=_fake_fetch({}))


# ---------------------------------------------------------------------------
# The honest boundary: interact steps are carried, never executed
# ---------------------------------------------------------------------------
def test_interact_step_becomes_an_envoy_package(store):
    plan = _plan(store)
    step = PF.add_step(store, OWNER, plan["id"], "interact",
                       "click the 'export' button")
    carried = PF.execute_step(store, OWNER, step["id"])
    assert carried["status"] == "carried"
    assert "never executed by Pathfinder" in carried["evidence"]
    pkg_id = int(carried["evidence"].split("envoy package ")[1]
                 .split(" ")[0])
    pkg = E.get_package(store, OWNER, pkg_id)
    assert pkg["destination"] == "external"
    assert "click the 'export' button" in pkg["body"]
    assert pkg["state"] == "draft"  # Rowan still has to carry it


def test_pathfinder_makes_no_provider_calls(store):
    # v1 fetches only; the provider budget is a cap for the future,
    # never spent here. If this ever dispatches, this test fails.
    plan = _plan(store)
    step = PF.add_step(store, OWNER, plan["id"], "fetch",
                       "http://example.com/page")
    before = store._db.execute(
        "SELECT COUNT(*) AS n FROM broker_usage").fetchone()["n"]
    PF.execute_step(store, OWNER, step["id"],
                    fetcher=_fake_fetch({"http://example.com/page": "x"}))
    after = store._db.execute(
        "SELECT COUNT(*) AS n FROM broker_usage").fetchone()["n"]
    assert after == before
