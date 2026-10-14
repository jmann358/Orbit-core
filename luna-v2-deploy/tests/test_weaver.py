"""Tests for the Weaver specialist (luna_v2/weaver.py).

Weaver proposes; Archivist files. The tests pin: deterministic theme
mining with citations, dedupe against already-proposed patterns, the
blank-approver refusal (nothing written), filing ONLY through
Archivist's file_memory (spy-pinned — Weaver never writes
memory_entries directly), and the no-pattern honest empty list.
"""

import json

from luna_v2 import archivist as AR
from luna_v2 import missions as M
from luna_v2 import weaver as WE
from luna_v2.store import Store

import pytest

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _file(store, text):
    return AR.file_memory(store, OWNER, text, approved_by="jason")


# ---------------------------------------------------------------------------
# Mining
# ---------------------------------------------------------------------------
def test_mine_finds_a_recurring_theme_with_citations(store):
    _file(store, "storm watch: the braced snapshot routine ran clean")
    _file(store, "storm outlook: friday flagged for thunderstorms")
    _file(store, "unrelated note about pizza")
    new = WE.mine(store, OWNER)
    themes = {n["pattern"]: json.loads(n["evidence"]) for n in new}
    storm = next(p for p in themes if "'storm'" in p)
    ev = themes[storm]
    assert ev["count"] >= 2
    assert len(ev["records"]) >= 2
    assert all(r["kind"] == "memory" for r in ev["records"])


def test_mine_dedupes_against_already_proposed(store):
    _file(store, "storm watch braced routine ran clean again")
    _file(store, "storm outlook friday flagged thunderstorms again")
    first = WE.mine(store, OWNER)
    assert first
    second = WE.mine(store, OWNER)
    assert second == []  # same themes, already proposed


def test_mine_with_no_pattern_returns_honest_empty(store):
    _file(store, "one short note")
    _file(store, "something entirely different")
    assert WE.mine(store, OWNER) == []


def test_mine_mines_mission_titles_too(store):
    M.create_mission(store, OWNER, "storm preparation sweep")
    _file(store, "storm watch braced routine ran clean")
    _file(store, "storm outlook friday flagged thunderstorms")
    new = WE.mine(store, OWNER)
    tokens = {json.loads(n["evidence"])["token"] for n in new}
    assert "storm" in tokens
    storm = next(n for n in new
                 if json.loads(n["evidence"])["token"] == "storm")
    kinds = {r["kind"] for r in json.loads(storm["evidence"])["records"]}
    assert "mission" in kinds  # the mission title fed the theme too


# ---------------------------------------------------------------------------
# Filing: through the Archivist only
# ---------------------------------------------------------------------------
def test_file_pattern_needs_a_named_approver(store):
    _file(store, "storm watch braced routine ran clean")
    _file(store, "storm outlook friday flagged thunderstorms")
    proposal = WE.mine(store, OWNER)[0]
    with pytest.raises(WE.ProposalRefused):
        WE.file_pattern(store, OWNER, proposal["id"], "   ")
    again = WE.list_proposals(store, OWNER)[0]
    assert again["status"] == "proposed"  # untouched


def test_file_pattern_goes_through_archivist_only(store, monkeypatch):
    seen = {}

    def spy(store_, owner_, text, **kwargs):
        seen["text"] = text
        seen["approved_by"] = kwargs.get("approved_by")
        return 4242

    _file(store, "storm watch braced routine ran clean")
    _file(store, "storm outlook friday flagged thunderstorms")
    proposal = WE.mine(store, OWNER)[0]
    monkeypatch.setattr(AR, "file_memory", spy)
    filed = WE.file_pattern(store, OWNER, proposal["id"], "jason")
    assert seen["approved_by"] == "jason"
    assert "storm" in seen["text"]
    assert filed["status"] == "filed"
    assert filed["filed_memory_id"] == 4242


def test_weaver_never_writes_memory_entries_directly():
    import luna_v2.weaver as wmod
    src = open(wmod.__file__).read()
    assert "INSERT INTO memory_entries" not in src
    assert "retire_memory" not in src


def test_file_pattern_only_on_proposed(store):
    _file(store, "storm watch braced routine ran clean")
    _file(store, "storm outlook friday flagged thunderstorms")
    proposal = WE.mine(store, OWNER)[0]
    WE.dismiss(store, OWNER, proposal["id"])
    with pytest.raises(WE.ProposalRefused):
        WE.file_pattern(store, OWNER, proposal["id"], "jason")
    with pytest.raises(WE.ProposalNotFound):
        WE.file_pattern(store, OWNER, 4242, "jason")


def test_dismiss_keeps_history(store):
    _file(store, "storm watch braced routine ran clean")
    _file(store, "storm outlook friday flagged thunderstorms")
    proposal = WE.mine(store, OWNER)[0]
    row = WE.dismiss(store, OWNER, proposal["id"])
    assert row["status"] == "dismissed"
    assert len(WE.list_proposals(store, OWNER)) == 1
