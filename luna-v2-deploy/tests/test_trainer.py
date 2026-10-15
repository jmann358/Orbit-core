"""Trainer: the capability coach's guards.

Jason's hire (2026-10-14): the Trainer designs capability-building
plans; he never grades, rewards, retires, assigns work, or spends
provider allocation. These tests pin those boundaries.
"""
import importlib

import pytest

from luna_v2 import trainer as TR
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "trainer.db"))
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Benchmarks: deterministic, evidence-honest
# ---------------------------------------------------------------------------
def test_benchmark_set_and_list(store):
    row = TR.set_benchmark(
        store, OWNER, "temporal_awareness",
        "Luna schedules and re-checks time-anchored events like a "
        "top-tier assistant does",
        evidence_level="unmeasured (storm timing code-correct, drill evidence pending)",
        gap_note="harvest stone S21: storm cadence is code-correct but dispatch-blind")
    assert row["area"] == "temporal_awareness"
    assert row["evidence_level"].startswith("unmeasured")
    rows = TR.list_benchmarks(store, OWNER)
    assert [r["area"] for r in rows] == ["temporal_awareness"]


def test_benchmark_is_deterministic(store):
    first = TR.set_benchmark(store, OWNER, "swarm_coordination",
                             "bar authored by Jason", "strong (receipt 9)")
    second = TR.set_benchmark(store, OWNER, "swarm_coordination",
                              "bar authored by Jason", "strong (receipt 9)")
    assert first["id"] == second["id"]
    rows = TR.list_benchmarks(store, OWNER)
    assert len(rows) == 1
    # Same area, new evidence -> overwrite, never a second row.
    TR.set_benchmark(store, OWNER, "swarm_coordination",
                     "bar authored by Jason", "strong (receipt 9, swarm 1)")
    assert len(TR.list_benchmarks(store, OWNER)) == 1
    assert TR.get_benchmark(store, OWNER, "swarm_coordination")[
        "evidence_level"] == "strong (receipt 9, swarm 1)"


def test_benchmark_no_evidence_means_unmeasured(store):
    row = TR.set_benchmark(store, OWNER, "deep_research",
                           "answers multi-step research like Muse does")
    assert row["evidence_level"] == "unmeasured"


def test_benchmark_refusals(store):
    with pytest.raises(TR.TrainerError):
        TR.set_benchmark(store, OWNER, "", "bar")
    with pytest.raises(TR.TrainerError):
        TR.set_benchmark(store, OWNER, "area", "")


def test_gap_summary_is_deterministic(store):
    TR.set_benchmark(store, OWNER, "b_area", "bar", "level one")
    TR.set_benchmark(store, OWNER, "a_area", "bar", "level two")
    first = TR.gap_summary(store, OWNER)
    second = TR.gap_summary(store, OWNER)
    assert first == second
    assert [g["area"] for g in first] == ["a_area", "b_area"]


# ---------------------------------------------------------------------------
# Plans: propose-only, decided by Jason/Rowan
# ---------------------------------------------------------------------------
def test_draft_plan_is_proposed_and_files_suggestion(store):
    row = TR.draft_plan(
        store, OWNER, "temporal_awareness",
        drills="run harvest S21 scenarios against the storm cadence code",
        success_measure="Luna re-checks a flagged day and reports the "
                        "re-check in a drill, approved by Rowan")
    assert row["status"] == "proposed"
    sugg = store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE check_name = ? "
        "AND status = 'open'", ("trainer_plan",)).fetchall()
    assert len(sugg) == 1
    assert "temporal_awareness" in sugg[0]["subject"]


def test_draft_plan_refusals(store):
    with pytest.raises(TR.TrainerError):
        TR.draft_plan(store, OWNER, "", "drills", "measure")
    with pytest.raises(TR.TrainerError):
        TR.draft_plan(store, OWNER, "target", "drills", "")


def test_decide_plan(store):
    row = TR.draft_plan(store, OWNER, "x", "drills", "measure")
    with pytest.raises(TR.TrainerError):
        TR.decide_plan(store, OWNER, row["id"], "approved", "")
    with pytest.raises(TR.TrainerError):
        TR.decide_plan(store, OWNER, row["id"], "approved", "trainer")
    with pytest.raises(TR.TrainerError):
        TR.decide_plan(store, OWNER, row["id"], "promote", "jason")
    done = TR.decide_plan(store, OWNER, row["id"], "approved", "jason")
    assert done["status"] == "approved"
    assert done["approved_by"] == "jason"
    closed = TR.decide_plan(store, OWNER, row["id"], "done", "rowan")
    assert closed["status"] == "done"
    assert closed["approved_by"] == "jason"  # approval stays on record
    with pytest.raises(TR.TrainerError):
        TR.decide_plan(store, OWNER, 9999, "approved", "jason")


def test_plan_lifecycle_listing(store):
    p1 = TR.draft_plan(store, OWNER, "a", "drills", "measure")
    p2 = TR.draft_plan(store, OWNER, "b", "drills", "measure")
    TR.decide_plan(store, OWNER, p1["id"], "dropped", "jason")
    assert len(TR.list_plans(store, OWNER)) == 2
    assert [p["id"] for p in TR.list_plans(store, OWNER, "proposed")] == [p2["id"]]
    assert [p["id"] for p in TR.list_plans(store, OWNER, "dropped")] == [p1["id"]]


# ---------------------------------------------------------------------------
# Structural: coach, never judge; zero spend
# ---------------------------------------------------------------------------
def _src():
    path = importlib.util.find_spec("luna_v2.trainer").origin
    with open(path) as f:
        return f.read()


def test_trainer_never_touches_grading_reward_or_review_paths():
    src = _src()
    # The Trainer grades nobody, rewards nobody, retires nobody.
    for token in ("mentor_grades", "reward_ledger", "review_cases"):
        assert token not in src, f"trainer.py mentions {token}"
    for ln in src.splitlines():
        assert not ln.startswith("from luna_v2 import mentor"), \
            "trainer.py imports the grader"
        assert not ln.startswith("import mentor"), \
            "trainer.py imports the grader"
        assert not ln.startswith("from luna_v2 import rewards"), \
            "trainer.py imports the rewards store"


def test_trainer_zero_provider_calls():
    src = _src()
    # Benchmark research routes through Scout/Cartographer; nothing here
    # spends allocation. No broker, no dispatch, no provider imports.
    assert "provider_dispatch" not in src
    assert "broker" not in src
    for ln in src.splitlines():
        assert not ln.startswith("from luna_v2 import dispatch"), \
            "trainer.py imports the dispatch layer"
