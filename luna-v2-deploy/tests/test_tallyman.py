"""Tallyman: the court's efficiency officer's guards.

Jason's hire (2026-10-14): the Tallyman tracks the operation's burn and
files efficiency proposals — propose-only forever, zero provider calls,
own-table writes only. Burn is not quality: he proposes, never grades,
never routes, never executes.
"""
import importlib.util

import pytest

from luna_v2 import tallyman as TM
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "tallyman.db"))
    yield s
    s.close()


def _snap(s, **kw):
    args = {"who": "rowan", "metric": "weekly_usage_pct",
            "value": 83.0, "unit": "%", "source": "jason"}
    args.update(kw)
    return TM.record_snapshot(s, OWNER, **args)


# Lifecycle ---------------------------------------------------------------
def test_snapshot_records_honest_source(store):
    r = _snap(store)
    assert r["who"] == "rowan"
    assert r["metric"] == "weekly_usage_pct"
    assert r["value"] == 83.0
    assert r["unit"] == "%"
    assert r["source"] == "jason"  # Jason said it — the record says who


def test_snapshot_refusals(store):
    with pytest.raises(TM.TallymanError):
        TM.record_snapshot(store, OWNER, "luna_court", "x", 1.0,
                           source="jason")  # bad who
    with pytest.raises(TM.TallymanError):
        TM.record_snapshot(store, OWNER, "rowan", "", 1.0,
                           source="jason")  # no metric
    with pytest.raises(TM.TallymanError):
        TM.record_snapshot(store, OWNER, "rowan", "m", "a lot",
                           source="jason")  # not numeric
    with pytest.raises(TM.TallymanError):
        TM.record_snapshot(store, OWNER, "rowan", "m", 1.0,
                           source="")  # no source


def test_proposal_lifecycle(store):
    p = TM.file_proposal(store, OWNER, "Batch the pointer loop",
                         "pre-stage byte-verified work batches",
                         projected_saving="~2-4 monitor sessions per sync")
    assert p["status"] == "draft"
    p = TM.propose(store, OWNER, p["id"])
    assert p["status"] == "proposed"
    p = TM.decide(store, OWNER, p["id"], "accepted", decided_by="jason")
    assert p["status"] == "decided"
    assert p["decision"] == "accepted"
    assert p["decided_by"] == "jason"


def test_proposal_refusals(store):
    p = TM.file_proposal(store, OWNER, "T", "body")
    # only drafts can be proposed, only proposed rows can be decided
    with pytest.raises(TM.TallymanError):
        TM.decide(store, OWNER, p["id"], "accepted", decided_by="jason")
    TM.propose(store, OWNER, p["id"])
    with pytest.raises(TM.TallymanError):
        TM.propose(store, OWNER, p["id"])  # already proposed
    # THE guard: the Tallyman never decides his own proposals
    with pytest.raises(TM.TallymanError):
        TM.decide(store, OWNER, p["id"], "accepted", decided_by="tallyman")
    with pytest.raises(TM.TallymanError):
        TM.decide(store, OWNER, p["id"], "accepted", decided_by="")
    with pytest.raises(TM.TallymanError):
        TM.decide(store, OWNER, p["id"], "maybe", decided_by="jason")
    # unknown rows fail cleanly
    with pytest.raises(TM.TallymanError):
        TM.propose(store, OWNER, 9999)


def test_list_filters(store):
    _snap(store)
    _snap(store, who="luna", metric="broker_calls", value=0.0,
          unit="calls", source="ledger")
    assert len(TM.list_snapshots(store, OWNER)) == 2
    assert len(TM.list_snapshots(store, OWNER, who="rowan")) == 1
    assert len(TM.list_snapshots(store, OWNER, metric="broker_calls")) == 1
    TM.file_proposal(store, OWNER, "A", "body")
    TM.file_proposal(store, OWNER, "B", "body")
    assert len(TM.list_proposals(store, OWNER, status="draft")) == 2
    assert len(TM.list_proposals(store, OWNER, status="proposed")) == 0
    with pytest.raises(TM.TallymanError):
        TM.list_proposals(store, OWNER, status="pending")


def test_report_is_deterministic(store):
    _snap(store)
    TM.file_proposal(store, OWNER, "Batch the pointer loop", "body",
                     projected_saving="~2-4 sessions")
    first = TM.report(store, OWNER)
    second = TM.report(store, OWNER)
    assert first == second
    assert "83.0 %" in first
    assert "source: jason" in first
    assert "Batch the pointer loop" in first


def test_report_latest_per_metric(store):
    _snap(store, value=9.0)   # older reading
    _snap(store, value=83.0)  # newest reading
    out = TM.report(store, OWNER)
    assert "83.0 %" in out
    assert "9.0 %" not in out  # the report shows the latest, not the history


def test_report_with_no_data(store):
    out = TM.report(store, OWNER)
    assert "No usage snapshots recorded yet." in out
    assert "No open efficiency proposals." in out


# Structural: own-table writes, zero provider calls, propose-only --------
def _src():
    path = importlib.util.find_spec("luna_v2.tallyman").origin
    with open(path) as f:
        return f.read()


def test_tallyman_never_writes_foreign_tables():
    src = _src()
    # no dispatch / grading / routing layers, ever. (missions is the
    # shared error family — medic.py imports it too; it's not a layer.)
    for mod in ("dispatch", "conductor", "mentor", "quartermaster",
                "rewards"):
        assert f"from luna_v2 import {mod}" not in src, \
            f"tallyman.py imports {mod}"
    for table in ("broker_ledger", "value_ledger", "guardian_suggestions",
                  "mentor_grades", "missions"):
        for stmt in ("INSERT INTO", "DELETE FROM"):
            assert f"{stmt} {table}" not in src, \
                f"tallyman.py writes {stmt} {table}"
    # own-table writes only: every UPDATE names his own proposals table
    for ln in src.splitlines():
        if "UPDATE " in ln:
            assert "UPDATE efficiency_proposals" in ln, \
                f"unexpected write: {ln!r}"


def test_tallyman_zero_provider_calls():
    src = _src()
    assert "provider_dispatch" not in src
    assert "broker.py" not in src
    assert "groq_chat" not in src
    assert "urllib" not in src
    assert "requests" not in src
