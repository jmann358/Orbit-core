"""Tests for Luna v2's specialist framework and the first active
specialist, the Research Scout.

No network anywhere: fetching and provider calls are injected fakes.
"""

import json

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import missions as M
from luna_v2 import specialists as SP
from luna_v2.specialists import FetchFailure, SpecialistNotActive, \
    SpecialistNotFound, BudgetExceeded

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    B.seed_providers(s, OWNER)
    yield s
    s.close()


def fake_fetcher_factory(pages, calls):
    """fetcher(url) -> text for known pages, FetchFailure otherwise."""
    def fake(url):
        calls.append(url)
        if url in pages:
            return pages[url]
        raise FetchFailure(f"cannot fetch {url}")
    return fake


def fake_transport_factory(calls, text="the digest", usage=None):
    usage = dict(usage or {"requests": 1.0, "tokens": 50.0})

    def fake(provider, prompt):
        calls.append((provider, prompt))
        return text, dict(usage)

    return fake


def usage_rows(s):
    return s._db.execute(
        "SELECT * FROM broker_usage WHERE owner = ?", (OWNER,)).fetchall()


def run_rows(s):
    return s._db.execute(
        "SELECT * FROM specialist_runs WHERE owner = ?", (OWNER,)).fetchall()


# ---------------------------------------------------------------------------
# (a) happy path
# ---------------------------------------------------------------------------
def test_scout_happy_path_records_run_and_usage(store):
    mid = store.create_mission(OWNER, "research", "a digest")
    fetches, calls = [], []
    result = SP.run_scout(
        store, "what is Luna?", ["http://a", "http://b"],
        owner=OWNER, mission_id=mid,
        transport=fake_transport_factory(calls),
        fetcher=fake_fetcher_factory({"http://a": "Luna is Luna v2",
                                      "http://b": "Luna runs missions"},
                                     fetches))
    assert result.digest == "the digest"
    assert result.provider == "groq"
    assert len(calls) == 1  # exactly one provider call in v1
    assert fetches == ["http://a", "http://b"]

    rows = run_rows(store)
    assert len(rows) == 1
    assert rows[0]["specialist"] == "scout"
    assert rows[0]["status"] == "done"
    assert rows[0]["result"] == "the digest"
    assert rows[0]["mission_id"] == mid

    used = usage_rows(store)
    assert used  # usage recorded through the broker
    assert all(r["mission_id"] == mid for r in used)  # mission-attributed
    assert store.list_ledger(OWNER)  # and a resource-ledger entry
    # the question and both source texts reached the provider
    assert "what is Luna?" in calls[0][1]
    assert "Luna is Luna v2" in calls[0][1]


# ---------------------------------------------------------------------------
# (b) all fetches fail -> run failed, zero provider calls, zero usage
# ---------------------------------------------------------------------------
def test_scout_all_fetches_fail_is_fail_closed(store):
    fetches, calls = [], []
    with pytest.raises(FetchFailure):
        SP.run_scout(
            store, "what?", ["http://dead1", "http://dead2"],
            owner=OWNER, transport=fake_transport_factory(calls),
            fetcher=fake_fetcher_factory({}, fetches))
    assert fetches == ["http://dead1", "http://dead2"]
    assert calls == []          # no provider call
    assert usage_rows(store) == []      # zero usage recorded
    assert store.list_ledger(OWNER) == []
    rows = run_rows(store)
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert "http://dead1" in rows[0]["error"]


# ---------------------------------------------------------------------------
# (c) budget refusal happens before any fetch or call
# ---------------------------------------------------------------------------
def test_scout_budget_refusal_has_no_side_effects(store):
    urls = [f"http://x{i}" for i in range(6)]
    fetches, calls = [], []
    with pytest.raises(BudgetExceeded):
        SP.run_scout(
            store, "what?", urls, owner=OWNER,
            transport=fake_transport_factory(calls),
            fetcher=fake_fetcher_factory({}, fetches))
    assert fetches == []
    assert calls == []
    assert run_rows(store) == []       # not even a run row
    assert usage_rows(store) == []


# ---------------------------------------------------------------------------
# (d) planned and unknown specialists refuse with no side effects
# ---------------------------------------------------------------------------
def test_planned_specialist_refuses(store, monkeypatch):
    monkeypatch.setattr(SP.SPECIALISTS["builder"], "status", "planned")
    calls = []
    with pytest.raises(SpecialistNotActive):
        SP.run_specialist("builder", "write code", ["http://a"],
                          store=store, owner=OWNER,
                          transport=fake_transport_factory(calls))
    assert calls == []
    assert run_rows(store) == []
    assert usage_rows(store) == []


def test_runnerless_active_specialist_refuses_cleanly(store):
    # Builder is active but works through its own module API; the
    # single-run dispatcher must refuse cleanly, with no side effects.
    calls = []
    with pytest.raises(SP.SpecialistError):
        SP.run_specialist("builder", "write code", ["http://a"],
                          store=store, owner=OWNER,
                          transport=fake_transport_factory(calls))
    assert calls == []
    assert run_rows(store) == []
    assert usage_rows(store) == []


def test_unknown_specialist_refuses(store):
    with pytest.raises(SpecialistNotFound):
        SP.run_specialist("oracle", "tell me", [], store=store)


# ---------------------------------------------------------------------------
# (e) mission integration: routine step completes with the digest
# ---------------------------------------------------------------------------
def test_scout_completes_routine_step_with_digest(store):
    m = M.create_mission(store, OWNER, "mission", "outcome")
    st = M.add_step(store, OWNER, m.id, "research the thing", "routine")
    calls = []
    result = SP.run_scout(
        store, "the thing?", ["http://a"], owner=OWNER,
        mission_id=m.id, step_id=st.id,
        transport=fake_transport_factory(calls, text="digest text"),
        fetcher=fake_fetcher_factory({"http://a": "source a"}, []))
    done = store.get_step(st.id)
    assert done["status"] == "done"
    assert done["evidence"] == "digest text" == result.digest


# ---------------------------------------------------------------------------
# (f) partial fetch failure: succeeds on survivors, failure noted
# ---------------------------------------------------------------------------
def test_scout_partial_fetch_failure_noted(store):
    calls = []
    result = SP.run_scout(
        store, "q?", ["http://good", "http://bad"], owner=OWNER,
        transport=fake_transport_factory(calls),
        fetcher=fake_fetcher_factory({"http://good": "good text"}, []))
    assert len(calls) == 1
    assert result.fetch_failures == [
        {"url": "http://bad", "error": "cannot fetch http://bad"}]
    assert "good text" in calls[0][1]
    assert "http://bad" not in calls[0][1]  # failed source not sent
    row = run_rows(store)[0]
    assert row["status"] == "done"
    sources = json.loads(row["sources_json"])
    bad = [s for s in sources if s["url"] == "http://bad"][0]
    assert bad["ok"] is False and bad["error"] == "cannot fetch http://bad"
    good = [s for s in sources if s["url"] == "http://good"][0]
    assert good["ok"] is True


# ---------------------------------------------------------------------------
# (g) the approved team roster
# ---------------------------------------------------------------------------
def test_roster_has_fifteen_profiles_all_active():
    profiles = SP.list_specialists()
    assert len(profiles) == 15
    by_name = {p.name: p for p in profiles}
    assert set(by_name) == {"scout", "verifier", "builder",
                            "quartermaster", "archivist", "watchman",
                            "envoy", "designer", "guardian",
                            "armorer", "scheduler", "operator",
                            "mentor", "sentinel", "host"}
    active = [p for p in profiles if p.status == "active"]
    assert [p.name for p in active] == ["scout", "verifier", "builder", "quartermaster", "archivist", "watchman", "envoy", "designer", "guardian", "armorer", "scheduler", "operator", "mentor", "sentinel", "host"]
    guardian = by_name["guardian"]
    assert guardian.tools == ["state_inspection", "suggestion_filing"]
    assert (guardian.max_provider_calls_per_run,
            guardian.max_fetches_per_run) == (1, 0)
    envoy = by_name["envoy"]
    assert envoy.tools == ["task_handoff", "message_drafting"]
    assert (envoy.max_provider_calls_per_run,
            envoy.max_fetches_per_run) == (3, 0)
    designer = by_name["designer"]
    assert designer.tools == ["design_proposals"]
    assert (designer.max_provider_calls_per_run,
            designer.max_fetches_per_run) == (3, 0)
    scout = by_name["scout"]
    assert (scout.max_provider_calls_per_run,
            scout.max_fetches_per_run) == (3, 5)


# ---------------------------------------------------------------------------
# (h) a missions refusal surfaces and is marked on the run record
# ---------------------------------------------------------------------------
def test_scout_step_refusal_surfaces_and_marks_run(store):
    m = M.create_mission(store, OWNER, "mission", "outcome")
    st = M.add_step(store, OWNER, m.id, "draft the risky thing",
                    "consequential")  # no approval -> must refuse
    calls = []
    with pytest.raises(M.StepNotApproved):
        SP.run_scout(
            store, "q?", ["http://a"], owner=OWNER,
            mission_id=m.id, step_id=st.id,
            transport=fake_transport_factory(calls),
            fetcher=fake_fetcher_factory({"http://a": "text"}, []))
    assert len(calls) == 1  # the research still ran and was accounted
    row = run_rows(store)[0]
    assert row["status"] == "done"
    assert f"step {st.id}" in row["error"]
    assert store.get_step(st.id)["status"] == "open"  # untouched


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------
def test_cli_specialists_lists_team(tmp_path, capsys, monkeypatch):
    db = str(tmp_path / "cli.db")

    from luna_v2 import cli
    assert cli.main(["--db", db, "--owner", OWNER, "specialists"]) == 0
    out = capsys.readouterr().out
    assert "scout — Research Scout [ACTIVE]" in out
    assert "envoy — Envoy [ACTIVE]" in out
    assert "designer — Designer [ACTIVE]" in out


def test_cli_scout_runs_and_prints(tmp_path, capsys, monkeypatch):
    db = str(tmp_path / "cli.db")
    calls = []

    from luna_v2 import cli
    monkeypatch.setattr(
        cli, "_default_transport",
        lambda store, owner: fake_transport_factory(calls))
    monkeypatch.setattr(
        SP, "default_fetcher",
        lambda url: f"fake content from {url}")
    rc = cli.main(["--db", db, "--owner", OWNER, "scout",
                   "what is it?", "--url", "http://a",
                   "--url", "http://b"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "scout run" in out
    assert "the digest" in out
    assert len(calls) == 1  # one provider call through the CLI path
    s = Store(db)
    try:
        rows = s._db.execute("SELECT * FROM specialist_runs").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "done"
        assert rows[0]["result"] == "the digest"
    finally:
        s.close()
