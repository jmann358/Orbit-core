"""Tests for the Artificer: interface drafts, light first.

The heavy-park rule is the point: a heavy propose is forced to
parked no matter what the caller asked, a parked draft refuses
selection, and only a re-score unparks it. All the fun of a master
interface, none of the drain.
"""

import os
import tempfile

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import artificer as A

OWNER = "jason"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _light(s, name="Command Deck"):
    return A.propose(s, OWNER, name, "one screen", "JARVIS", "light",
                     cpu_note="static", wifi_note="loads once")


# ---------------------------------------------------------------------------
# The heavy-park law
# ---------------------------------------------------------------------------
def test_heavy_propose_forced_parked(store):
    row = A.propose(store, OWNER, "Live Hologram", "full 3d",
                    "sci-fi", "heavy",
                    cpu_note="melts the mac", wifi_note="streams forever")
    assert row["status"] == "parked"
    assert "saved for later \u2014 too heavy for now" in row["notes"]


def test_select_parked_refused(store):
    row = A.propose(store, OWNER, "Live Hologram", "full 3d",
                    "sci-fi", "heavy")
    with pytest.raises(M.LunaError):
        A.select_draft(store, OWNER, row["id"])
    assert A.get_draft(store, OWNER, row["id"])["status"] == "parked"


def test_propose_bad_cost_refused(store):
    with pytest.raises(M.LunaError):
        A.propose(store, OWNER, "X", "y", "z", "medium-heavy")


def test_propose_duplicate_name_refused(store):
    _light(store)
    with pytest.raises(M.LunaError):
        _light(store)


# ---------------------------------------------------------------------------
# Selection and re-scoring
# ---------------------------------------------------------------------------
def test_select_light_works_and_is_exclusive(store):
    a = _light(store, "Command Deck")
    b = _light(store, "Party Screen")
    A.select_draft(store, OWNER, a["id"])
    assert A.get_draft(store, OWNER, a["id"])["status"] == "selected"
    A.select_draft(store, OWNER, b["id"])
    assert A.get_draft(store, OWNER, b["id"])["status"] == "selected"
    assert A.get_draft(store, OWNER, a["id"])["status"] == "draft"


def test_rescore_heavy_to_light_unparks(store):
    row = A.propose(store, OWNER, "Live Hologram", "full 3d",
                    "sci-fi", "heavy")
    out = A.rescore(store, OWNER, row["id"], "light",
                    cpu_note="actually static", wifi_note="loads once")
    assert out["cost"] == "light"
    assert out["status"] == "draft"
    # and now it can be selected
    sel = A.select_draft(store, OWNER, row["id"])
    assert sel["status"] == "selected"


def test_rescore_light_to_heavy_parks(store):
    row = _light(store)
    out = A.rescore(store, OWNER, row["id"], "heavy")
    # the heavy-park law applies to re-scores too — no escape hatch
    assert out["cost"] == "heavy"
    assert out["status"] == "parked"
    assert "saved for later \u2014 too heavy for now" in out["notes"]
    with pytest.raises(M.LunaError):
        A.select_draft(store, OWNER, row["id"])


def test_select_unknown_draft_refused(store):
    with pytest.raises(M.LunaError):
        A.select_draft(store, OWNER, 9999)


# ---------------------------------------------------------------------------
# Seed concepts
# ---------------------------------------------------------------------------
def test_seed_idempotent(store):
    first = A.seed_concepts(store, OWNER)
    second = A.seed_concepts(store, OWNER)
    assert len(first) == 3 == len(second)
    names = [r["name"] for r in first]
    assert names == ["Command Deck", "Party Screen", "Court Overview"]
    assert all(r["cost"] == "light" and r["status"] == "draft"
               for r in first)
    assert "JARVIS" in first[0]["theme_source"]
    assert "Pok\u00e9mon" in first[1]["theme_source"]
    assert "original" in first[2]["theme_source"]


def test_seed_does_not_clobber_user_drafts(store):
    A.seed_concepts(store, OWNER)
    _light(store, "My Deck")
    rows = A.list_drafts(store, OWNER)
    assert len(rows) == 4
