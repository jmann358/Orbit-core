"""Tests for the Armorer specialist (luna_v2/armorer.py).

Armorer inventories Luna's real toolbox and health-checks it. The
default check is spend-free (file presence + a route_explain note);
the optional live probe runs exactly one tiny dispatch. Broken checks
are data, never exceptions — only API misuse raises ArmorerError.
"""

import os
from pathlib import Path

import pytest

from luna_v2 import armorer as A
from luna_v2 import broker as B
from luna_v2 import dispatch as D
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _present(path_text):
    try:
        return Path(os.path.expanduser(path_text)).exists()
    except OSError:
        return False


def _upsert_raw(store, owner, name, location, doc_path=""):
    A._ensure_schema(store)  # same package; schema must exist first
    store._db.execute(
        "INSERT OR REPLACE INTO armorer_tools (owner, name, kind, location, "
        "doc_path, status) VALUES (?, ?, 'test', ?, ?, 'unknown')",
        (owner, name, location, doc_path))
    store._db.commit()


def _fake_transport_factory(calls, usage=None):
    def transport(provider, prompt):
        calls.append((provider, prompt))
        return "pong", (usage if usage is not None
                        else {"requests": 1.0, "tokens": 100.0})
    return transport


def _plant_groq(store, tmp_path, owner=OWNER):
    """Register a groq-connector-helper row pointing at a file that
    really exists, independent of what this machine's toolbox seeds.
    The two probe/routability tests must not depend on the ambient
    machine having Rowan's helper file."""
    helper = tmp_path / "groq_chat.py"
    helper.write_text("# stand-in for the real connector helper\n")
    _upsert_raw(store, owner, "groq-connector-helper", str(helper))
    return helper


def _seedable_names():
    return [t["name"] for t in A.SEED_TOOLS if A.tool_is_seedable(t)]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def test_seed_is_idempotent_and_preserves_status(store):
    # A machine missing a helper file seeds fewer, truthful rows.
    seedable = _seedable_names()
    assert A.seed_tools(store, OWNER) == len(seedable)
    assert A.seed_tools(store, OWNER) == len(seedable)
    if not seedable:
        pytest.skip("no seedable tools on this machine")
    row = A.get_tool(store, OWNER, seedable[0])
    # Break one row manually: re-seeding must not touch it.
    store._db.execute("UPDATE armorer_tools SET status = 'broken', "
                      "detail = 'hand-placed' WHERE id = ?", (row["id"],))
    store._db.commit()
    assert A.seed_tools(store, OWNER) == len(seedable)
    again = A.get_tool(store, OWNER, seedable[0])
    assert again["status"] == "broken"
    assert again["detail"] == "hand-placed"


def test_seed_tables_match_seed_tools(store):
    A.seed_tools(store, OWNER)
    rows = A.list_tools(store, OWNER)
    assert {r["name"] for r in rows} == set(_seedable_names())
    assert all(r["status"] == "unknown" for r in rows)
    assert all(r["last_checked_at"] is None for r in rows)


def test_missing_helper_file_is_not_seeded(store, monkeypatch):
    """Portability pin (THRONE sync, Step 4): a machine without the
    helper file gets NO groq-connector-helper row at all — never a row
    that could only ever read 'broken'. The rest of the toolbox seeds
    untouched, and nothing raises."""
    real_exists = A._exists

    def fake_exists(path_text):
        if "groq_chat.py" in str(path_text):
            return False
        return real_exists(path_text)

    monkeypatch.setattr(A, "_exists", fake_exists)
    A.seed_tools(store, OWNER)
    assert A.get_tool(store, OWNER, "groq-connector-helper") is None
    names = {r["name"] for r in A.list_tools(store, OWNER)}
    assert "groq-connector-helper" not in names
    # Every other seedable tool still seeds, nothing else dropped.
    assert names == {t["name"] for t in A.SEED_TOOLS
                     if t["name"] != "groq-connector-helper"
                     and A.tool_is_seedable(t)}


def test_file_path_heuristic():
    assert A._location_is_file_path("~/x/y.py")
    assert A._location_is_file_path("/opt/x")
    assert A._location_is_file_path("rel/dir/file")
    assert not A._location_is_file_path("https://example.com/x")
    assert not A._location_is_file_path("api://service")
    assert not A._location_is_file_path("")


def test_seed_misuse_raises(store):
    with pytest.raises(A.ArmorerError):
        A.seed_tools(store, "")
    with pytest.raises(A.ArmorerError):
        A.check_tools(store, "", probe_transport=None)


# ---------------------------------------------------------------------------
# Spend-free checks on the real toolbox
# ---------------------------------------------------------------------------
def test_spend_free_check_marks_real_tools_ok(store):
    needed = [t["location"] for t in A.SEED_TOOLS]
    needed += [t["doc_path"] for t in A.SEED_TOOLS]
    missing = [p for p in needed if not _present(p)]
    if missing:
        pytest.skip(f"tool path(s) absent in this environment: {missing}")
    rows = A.check_tools(store, OWNER)
    assert len(rows) == 3
    assert all(r["status"] == "ok" for r in rows)
    assert all(r["last_checked_at"] for r in rows)
    for r in rows:
        assert r["location"] in r["detail"]


def test_bogus_location_is_broken_and_names_the_path(store):
    _upsert_raw(store, "test2", "phantom-cli", "/no/such/tool/anywhere")
    rows = A.check_tools(store, "test2")  # also seeds the real toolbox
    r = next(x for x in rows if x["name"] == "phantom-cli")
    assert r["status"] == "broken"
    assert "/no/such/tool/anywhere" in r["detail"]
    assert r["last_checked_at"]


def test_missing_doc_path_breaks_with_own_detail(store):
    # Location exists (this very file), doc does not.
    _upsert_raw(store, "test3", "docless", __file__, "/no/such/doc.md")
    rows = A.check_tools(store, "test3")
    r = rows[0]
    assert r["status"] == "broken"
    assert "/no/such/doc.md" in r["detail"]
    assert "doc_path missing" in r["detail"]


def test_broken_checks_never_raise(store):
    # Every planted tool bogus: check_tools returns rows, not exceptions.
    _upsert_raw(store, "test4", "one", "/no/tool/one")
    _upsert_raw(store, "test4", "two", "/no/tool/two", "/no/doc/two.md")
    rows = A.check_tools(store, "test4")
    planted = [r for r in rows if r["name"] in ("one", "two")]
    assert len(planted) == 2
    assert all(r["status"] == "broken" for r in planted)


def test_groq_detail_carries_spend_free_routability_note(store, tmp_path):
    B.seed_providers(store, OWNER)
    _plant_groq(store, tmp_path)
    rows = A.check_tools(store, OWNER)
    groq = next(r for r in rows if r["name"] == "groq-connector-helper")
    assert "route check:" in groq["detail"]
    assert "routable for reference job" in groq["detail"]


def test_groq_detail_notes_missing_inventory(store):
    # No broker seeding at all: the note says so, status still file-based.
    missing = [t["location"] for t in A.SEED_TOOLS
               if not _present(t["location"])]
    if missing:
        pytest.skip(f"tool path(s) absent in this environment: {missing}")
    rows = A.check_tools(store, OWNER)
    groq = next(r for r in rows if r["name"] == "groq-connector-helper")
    assert "no provider inventory" in groq["detail"]


# ---------------------------------------------------------------------------
# Live probe
# ---------------------------------------------------------------------------
def test_probe_success_makes_exactly_one_dispatch(store, tmp_path):
    B.seed_providers(store, OWNER)
    _plant_groq(store, tmp_path)
    calls = []
    rows = A.check_tools(store, OWNER,
                         probe_transport=_fake_transport_factory(calls))
    assert len(calls) == 1
    provider, prompt = calls[0]
    assert prompt == "ping"
    groq = next(r for r in rows if r["name"] == "groq-connector-helper")
    assert groq["status"] == "ok"
    assert "probe ok" in groq["detail"]
    assert provider in groq["detail"]
    # The probe's usage flowed through the broker's normal accounting.
    used = store.usage_sum(OWNER, provider, "requests",
                           "2000-01-01T00:00:00+00:00",
                           "2999-01-01T00:00:00+00:00")
    assert used == 1.0


def test_probe_failure_marks_groq_broken_with_error(store, tmp_path):
    B.seed_providers(store, OWNER)
    _plant_groq(store, tmp_path)

    def failing(provider, prompt):
        raise D.DispatchError("boom: network down")

    rows = A.check_tools(store, OWNER, probe_transport=failing)
    groq = next(r for r in rows if r["name"] == "groq-connector-helper")
    assert groq["status"] == "broken"
    assert "boom: network down" in groq["detail"]
    # Nothing was recorded for the failed call.
    used = store.usage_sum(OWNER, "groq", "requests",
                           "2000-01-01T00:00:00+00:00",
                           "2999-01-01T00:00:00+00:00")
    assert used == 0.0


def test_no_probe_means_no_dispatch(store, tmp_path):
    B.seed_providers(store, OWNER)
    _plant_groq(store, tmp_path)
    calls = []
    rows = A.check_tools(store, OWNER, probe_transport=None)
    _ = _fake_transport_factory(calls)  # exists, but never handed over
    assert calls == []
    groq = next(r for r in rows if r["name"] == "groq-connector-helper")
    # No probe ran: neither probe outcome marker may appear in the
    # detail. (The location itself echoes the pytest tmp dir, whose
    # name contains this test's name, so a bare "probe" substring
    # check would be a false positive.)
    assert "probe ok" not in groq["detail"]
    assert "probe failed" not in groq["detail"]


def test_probe_transport_must_be_callable(store):
    with pytest.raises(A.ArmorerError):
        A.check_tools(store, OWNER, probe_transport="not-a-transport")


# ---------------------------------------------------------------------------
# Rendering helper
# ---------------------------------------------------------------------------
def test_render_text_names_every_tool(store):
    A.seed_tools(store, OWNER)
    text = A.render_text(A.list_tools(store, OWNER))
    seedable = [t for t in A.SEED_TOOLS if A.tool_is_seedable(t)]
    for t in seedable:
        assert t["name"] in text
    if not seedable:
        assert text == "no tools inventoried"
    assert A.render_text([]) == "no tools inventoried"
