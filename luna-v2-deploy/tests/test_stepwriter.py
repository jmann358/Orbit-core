"""Stepwriter: one plain sentence in, a draft mission out.

Jason's own complaint (2026-10-14): the web flow made him invent a
"subject" and then WRITE A STEP himself. The Stepwriter is the
planner: drafts are propose-only, kinds are flagged conservatively,
and nothing self-files.
"""
import importlib

import pytest

from luna_v2 import stepwriter as SW
from luna_v2.store import Store

OWNER = "jason"
SENTENCE = "can we work on connecting to muse?"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "stepwriter.db"))
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Decomposition: deterministic, offline, conservative
# ---------------------------------------------------------------------------
def test_draft_is_deterministic(store):
    a = SW.draft_mission(store, OWNER, SENTENCE)
    b = SW.draft_mission(store, OWNER, SENTENCE)
    assert a["status"] == "draft"
    assert (a["title"], a["outcome"]) == (b["title"], b["outcome"])
    assert [(s["description"], s["kind"]) for s in a["steps"]] == \
           [(s["description"], s["kind"]) for s in b["steps"]]


def test_jason_sentence_drafts_a_connect_plan(store):
    d = SW.draft_mission(store, OWNER, SENTENCE)
    assert d["title"] == "Connect muse"
    assert "verified" in d["outcome"]
    kinds = [s["kind"] for s in d["steps"]]
    assert "consequential" in kinds  # test-scope connection is flagged
    assert all(s["kind"] in ("routine", "consequential") for s in d["steps"])
    # every consequential step says why, in plain words
    for s in d["steps"]:
        if s["kind"] == "consequential":
            assert s["flagged_because"]


def test_template_fallback_on_dead_provider(store):
    # use_provider=True but the scratch DB has no routed provider:
    # fail-closed -> the deterministic templates still yield a draft,
    # and nothing is spent.
    d = SW.draft_mission(store, OWNER, SENTENCE, use_provider=True)
    assert d["title"] == "Connect muse"
    assert d["status"] == "draft"


def test_zero_provider_calls_on_fallback(store):
    def _ledger():
        row = store._db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='broker_usage'").fetchone()
        if row is None:
            return []
        return store._db.execute(
            "SELECT * FROM broker_usage WHERE owner = ?", (OWNER,)
        ).fetchall()
    before = _ledger()
    SW.draft_mission(store, OWNER, SENTENCE, use_provider=True)
    assert _ledger() == before


def test_conservative_flagging_when_unsure(store):
    d = SW.draft_mission(store, OWNER, "do something about the thing")
    assert d["status"] == "draft"
    assert d["steps"][0]["kind"] == "consequential"
    assert d["steps"][0]["flagged_because"]


def test_draft_refusals(store):
    with pytest.raises(SW.StepwriterError):
        SW.draft_mission(store, OWNER, "")
    with pytest.raises(SW.StepwriterError):
        SW.draft_mission(store, OWNER, "   ")
    with pytest.raises(SW.StepwriterError):
        SW.get_draft(store, OWNER, 9999)


# ---------------------------------------------------------------------------
# Approve -> file: the ONLY path to a real mission
# ---------------------------------------------------------------------------
def test_draft_never_self_files(store):
    before = store._db.execute(
        "SELECT COUNT(*) AS c FROM missions").fetchone()["c"]
    SW.draft_mission(store, OWNER, SENTENCE)
    assert store._db.execute(
        "SELECT COUNT(*) AS c FROM missions").fetchone()["c"] == before


def test_file_needs_approval_and_a_named_approver(store):
    d = SW.draft_mission(store, OWNER, SENTENCE)
    with pytest.raises(SW.StepwriterError):
        SW.file_draft(store, OWNER, d["id"], "jason")  # not approved yet
    with pytest.raises(SW.StepwriterError):
        SW.approve_draft(store, OWNER, d["id"], "")  # blank approver
    with pytest.raises(SW.StepwriterError):
        SW.approve_draft(store, OWNER, d["id"], "stepwriter")  # self-approval
    approved = SW.approve_draft(store, OWNER, d["id"], "jason")
    assert approved["status"] == "approved"
    with pytest.raises(SW.StepwriterError):
        SW.file_draft(store, OWNER, d["id"], "rowan")  # wrong approver
    with pytest.raises(SW.StepwriterError):
        SW.file_draft(store, OWNER, d["id"], "")  # blank approver
    filed = SW.file_draft(store, OWNER, d["id"], "jason")
    assert filed["status"] == "filed"
    assert filed["mission_id"]
    m = store._db.execute(
        "SELECT * FROM missions WHERE id = ?",
        (filed["mission_id"],)).fetchone()
    assert m is not None and m["title"] == "Connect muse"
    steps = store._db.execute(
        "SELECT * FROM steps WHERE mission_id = ? ORDER BY seq",
        (filed["mission_id"],)).fetchall()
    assert len(steps) == len(d["steps"])
    kinds = {s["kind"] for s in steps}
    assert kinds <= {"routine", "consequential"}
    # filing twice is refused — the draft is spent
    with pytest.raises(SW.StepwriterError):
        SW.file_draft(store, OWNER, d["id"], "jason")


def test_reject_draft(store):
    d = SW.draft_mission(store, OWNER, SENTENCE)
    r = SW.reject_draft(store, OWNER, d["id"], "jason")
    assert r["status"] == "rejected"
    with pytest.raises(SW.StepwriterError):
        SW.file_draft(store, OWNER, d["id"], "jason")


def test_drafts_listed_by_status(store):
    a = SW.draft_mission(store, OWNER, SENTENCE)
    SW.draft_mission(store, OWNER, "research the storm")
    SW.approve_draft(store, OWNER, a["id"], "jason")
    assert len(SW.list_drafts(store, OWNER)) == 2
    assert len(SW.list_drafts(store, OWNER, "draft")) == 1
    assert len(SW.list_drafts(store, OWNER, "approved")) == 1
    with pytest.raises(SW.StepwriterError):
        SW.list_drafts(store, OWNER, "bogus")


# ---------------------------------------------------------------------------
# Structural: the mission-creating code lives only in file_draft
# ---------------------------------------------------------------------------
def test_nothing_self_files():
    path = importlib.util.find_spec("luna_v2.stepwriter").origin
    with open(path) as f:
        src = f.read()
    idx = src.index("def file_draft(")
    head, tail = src[:idx], src[idx:]
    assert "missions.create_mission(" not in head
    assert "missions.add_step(" not in head
    assert "missions.create_mission(" in tail  # the one allowed path
    assert "missions.add_step(" in tail


def test_budget_allows_one_dispatch_max():
    from luna_v2 import specialists as SP
    p = SP.get_profile("stepwriter")
    assert p.tools == ["mission_planning"]
    assert p.max_provider_calls_per_run == 1  # the brief's one-dispatch max
    assert p.max_fetches_per_run == 0
