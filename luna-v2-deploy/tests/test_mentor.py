"""Tests for Mentor: grades specialist runs deterministically and files
improvement drafts through Guardian. It may read specialist_runs and
write mentor_reviews + guardian_suggestions — nothing else."""
import pytest

from luna_v2.store import Store
from luna_v2 import guardian as G
from luna_v2 import mentor as MT
from luna_v2 import specialists as SP


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "mentor.db"))
    yield s
    s.close()


def _seed_run(store, specialist="scout", owner="jason", status="done",
              result="", error="", mission_id=None):
    SP._ensure_schema(store)
    cur = store._db.execute(
        "INSERT INTO specialist_runs (specialist, owner, mission_id, "
        "step_id, question, sources_json, status, result, error, "
        "created_at) VALUES (?, ?, ?, NULL, 'q', '[]', ?, ?, ?, ?)",
        (specialist, owner, mission_id, status, result, error,
         "2026-10-13T00:00:00+00:00"))
    store._db.commit()
    return cur.lastrowid


def _seed_every_branch(store):
    """One run per grade branch; returns run ids in seeding order."""
    ids = []
    ids.append(_seed_run(store, status="failed",
                         error="fetch failed\nretry later"))        # weak
    ids.append(_seed_run(store, status="started"))                    # weak
    ids.append(_seed_run(store, status="done", result=""))            # weak
    ids.append(_seed_run(store, status="done", result="digest here",
                         error="step 7 could not be completed: nope")) # ok
    ids.append(_seed_run(store, status="done", result="a fine digest",
                         mission_id=4))                              # strong
    return ids


def test_grade_all_branches(store):
    _seed_every_branch(store)
    grades = MT.grade_runs(store, "jason")
    assert len(grades) == 5
    by_id = {g["run_id"]: g for g in grades}
    # newest first
    assert [g["run_id"] for g in grades] == sorted(by_id, reverse=True)

    assert by_id[1]["grade"] == "weak"
    assert "fetch failed" in by_id[1]["reason"]
    assert "\n" not in by_id[1]["reason"]  # only the first line

    assert by_id[2]["grade"] == "weak"
    assert by_id[2]["reason"] == "run never finished"

    assert by_id[3]["grade"] == "weak"
    assert "empty result" in by_id[3]["reason"]

    assert by_id[4]["grade"] == "ok"
    assert "partial issue" in by_id[4]["reason"]

    assert by_id[5]["grade"] == "strong"
    assert by_id[5]["reason"] == "completed cleanly"
    # mission attribution is informational
    assert by_id[5]["mission_attributed"] is True
    assert by_id[1]["mission_attributed"] is False


def test_grade_window_limit(store):
    for _ in range(7):
        _seed_run(store, status="done", result="r")
    assert len(MT.grade_runs(store, "jason", limit=5)) == 5


def test_draft_files_one_suggestion_per_weak_specialist(store):
    _seed_run(store, specialist="scout", status="failed", error="boom")
    _seed_run(store, specialist="watchman", status="started")
    _seed_run(store, specialist="sentinel", status="done", result="clean")
    report = MT.draft_improvements(store, "jason")
    assert report["runs_graded"] == 3
    assert report["suggestions_filed"] == 2

    inbox = G.inbox(store, "jason")
    mentor_s = [r for r in inbox if r["check_name"] == "mentor_review"]
    assert len(mentor_s) == 2
    subjects = {r["subject"] for r in mentor_s}
    assert subjects == {"scout", "watchman"}
    for r in mentor_s:
        assert "Mentor never applies changes itself" in r["proposed_action"]


def test_draft_dedupe_second_call_files_nothing(store):
    _seed_run(store, specialist="scout", status="failed", error="boom")
    first = MT.draft_improvements(store, "jason")
    assert first["suggestions_filed"] == 1
    second = MT.draft_improvements(store, "jason")
    assert second["suggestions_filed"] == 0
    inbox = G.inbox(store, "jason")
    mentor_s = [r for r in inbox if r["check_name"] == "mentor_review"]
    assert len(mentor_s) == 1


def test_severity_majority_weak_warning_else_info(store):
    # scout: 2 weak of 3 -> warning
    _seed_run(store, specialist="scout", status="failed", error="a")
    _seed_run(store, specialist="scout", status="started")
    _seed_run(store, specialist="scout", status="done", result="fine")
    # watchman: 1 weak among 3 strong -> info
    _seed_run(store, specialist="watchman", status="done", result="ok")
    _seed_run(store, specialist="watchman", status="done", result="ok")
    _seed_run(store, specialist="watchman", status="done", result="ok")
    _seed_run(store, specialist="watchman", status="failed", error="blip")
    MT.draft_improvements(store, "jason")
    inbox = {r["subject"]: r for r in G.inbox(store, "jason")
             if r["check_name"] == "mentor_review"}
    assert inbox["scout"]["severity"] == "warning"
    assert inbox["watchman"]["severity"] == "info"
    assert "2 of the last 3" in inbox["scout"]["observation"]


def test_observation_names_pattern_and_evidence(store):
    _seed_run(store, specialist="scout", status="failed", error="timeout x")
    MT.draft_improvements(store, "jason")
    row = [r for r in G.inbox(store, "jason")
           if r["check_name"] == "mentor_review"][0]
    assert "scout" in row["observation"]
    assert "timeout x" in row["evidence"]


def test_purity_specialist_runs_untouched(store):
    _seed_run(store, specialist="scout", status="failed", error="boom")
    _seed_run(store, specialist="scout", status="done", result="fine")
    before = [dict(r) for r in store._db.execute(
        "SELECT * FROM specialist_runs").fetchall()]
    MT.grade_runs(store, "jason")
    MT.draft_improvements(store, "jason")
    after = [dict(r) for r in store._db.execute(
        "SELECT * FROM specialist_runs").fetchall()]
    assert before == after

    reviews = store._db.execute(
        "SELECT * FROM mentor_reviews").fetchall()
    assert len(reviews) == 1
    assert reviews[0]["runs_graded"] == 2
    assert reviews[0]["suggestions_filed"] == 1
    # the only new rows anywhere: mentor_reviews + the guardian suggestion
    n_suggestions = store._db.execute(
        "SELECT COUNT(*) c FROM guardian_suggestions").fetchone()["c"]
    assert n_suggestions == 1


def test_no_runs_records_empty_review(store):
    report = MT.draft_improvements(store, "jason")
    assert report["runs_graded"] == 0
    assert report["suggestions_filed"] == 0
    assert report["per_specialist"] == {}
    reviews = store._db.execute("SELECT * FROM mentor_reviews").fetchall()
    assert len(reviews) == 1
    assert reviews[0]["runs_graded"] == 0
    # Guardian's table only exists once something is filed — with no
    # weak runs there must be nothing in it (or no table at all).
    tbl = store._db.execute(
        "SELECT name FROM sqlite_master WHERE name = "
        "'guardian_suggestions'").fetchone()
    if tbl is not None:
        assert store._db.execute(
            "SELECT COUNT(*) c FROM guardian_suggestions"
        ).fetchone()["c"] == 0
