"""Tests for Mentor's review-and-retire upgrade (Jason's 2026-10-14
direction): persistent grades, threshold-driven review cases with
recommendations + redelegation drafts, Jason/Rowan-only decisions,
status overrides wired into the run framework, and the resource-tier
rewards throttle while a case is open. Jason's rules hold throughout:
Mentor never decides, earned rewards are never revoked, training
comes before removal."""
import sys

import pytest

from luna_v2.store import Store
from luna_v2 import broker as BK
from luna_v2 import mentor as MT
from luna_v2 import specialists as SP
from luna_v2 import builder as BL
from luna_v2 import rewards as RW
from luna_v2 import missions as M

OWNER = "jason"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "reviews.db"))
    BK.seed_providers(s, OWNER)
    yield s
    s.close()


def _seed_run(store, specialist="scout", status="done", result="",
              error=""):
    SP._ensure_schema(store)
    cur = store._db.execute(
        "INSERT INTO specialist_runs (specialist, owner, mission_id, "
        "step_id, question, sources_json, status, result, error, "
        "created_at) VALUES (?, ?, NULL, NULL, 'q', '[]', ?, ?, ?, ?)",
        (specialist, OWNER, status, result, error,
         "2026-10-14T00:00:00+00:00"))
    store._db.commit()
    return cur.lastrowid


def _weak_run(store, specialist="scout"):
    """A run that grades weak (done, empty result)."""
    return _seed_run(store, specialist, status="done", result="")


def _strong_run(store, specialist="scout"):
    return _seed_run(store, specialist, status="done",
                     result="digest here")


def _seed_mixed(store, specialist, n_weak, n_strong):
    for _ in range(n_weak):
        _weak_run(store, specialist)
    for _ in range(n_strong):
        _strong_run(store, specialist)


def _closed_mission(store):
    m = M.create_mission(store, OWNER, "proof", "outcome")
    step = M.add_step(store, OWNER, m.id, "a step", "routine")
    M.complete_step(store, step.id, "done", "evidence")
    M.close_mission(store, m.id)
    return m


def _fake_transport(text="the digest"):
    def transport(provider, prompt):
        return text, {"requests": 1.0, "tokens": 50.0}
    return transport


# ---------------------------------------------------------------------------
# Persistent grades
# ---------------------------------------------------------------------------
def test_grades_persist_and_are_idempotent(store):
    _weak_run(store)
    _strong_run(store)
    _seed_run(store, status="failed", error="boom")
    out = MT.persist_grades(store, OWNER)
    assert out == {"graded": 3, "persisted_new": 3}
    again = MT.persist_grades(store, OWNER)
    assert again == {"graded": 3, "persisted_new": 0}
    hist = MT.grade_history(store, OWNER)
    assert len(hist) == 3
    # newest first
    assert [h["run_id"] for h in hist] == sorted(
        [h["run_id"] for h in hist], reverse=True)
    assert {h["grade"] for h in hist} == {"weak", "strong"}


def test_grade_summary_counts(store):
    _seed_mixed(store, "verifier", n_weak=3, n_strong=7)
    MT.persist_grades(store, OWNER)
    sm = MT.grade_summary(store, OWNER, "verifier", last_n=10)
    assert sm["last_n"] == 10
    assert sm["counts"] == {"strong": 7, "ok": 0, "weak": 3}
    # windowing: 12 persisted, last 10 only
    _seed_mixed(store, "verifier", n_weak=0, n_strong=2)
    MT.persist_grades(store, OWNER)
    sm = MT.grade_summary(store, OWNER, "verifier", last_n=10)
    assert sm["last_n"] == 10
    assert sm["counts"]["strong"] + sm["counts"]["weak"] == 10


# ---------------------------------------------------------------------------
# Review cases: thresholds and recommendations
# ---------------------------------------------------------------------------
def test_no_case_below_trigger(store):
    _seed_mixed(store, "scout", n_weak=2, n_strong=8)
    out = MT.evaluate_reviews(store, OWNER)
    assert out["cases_opened"] == []
    assert MT.list_cases(store, OWNER) == []


def test_no_case_below_minimum_grades(store):
    _seed_mixed(store, "scout", n_weak=4, n_strong=0)
    out = MT.evaluate_reviews(store, OWNER)
    assert out["cases_opened"] == []


def test_train_case_at_three_weak(store):
    _seed_mixed(store, "scout", n_weak=3, n_strong=7)
    out = MT.evaluate_reviews(store, OWNER)
    assert len(out["cases_opened"]) == 1
    case = MT.open_case_for(store, OWNER, "scout")
    assert case is not None
    assert case["status"] == "open"
    assert case["recommendation"] == "train"  # 30% < 50%
    assert "3 of the last 10" in case["trigger_summary"]
    assert case["redelegation_plan"]  # draft saved on the case
    # one Guardian suggestion filed
    rows = store._db.execute(
        "SELECT check_name, severity FROM guardian_suggestions "
        "WHERE owner = ? AND subject = 'scout'", (OWNER,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["check_name"] == "mentor_review_case"
    assert rows[0]["severity"] == "warning"


def test_restrict_at_half_weak(store):
    _seed_mixed(store, "verifier", n_weak=5, n_strong=5)
    MT.evaluate_reviews(store, OWNER)
    assert MT.open_case_for(store, OWNER, "verifier")["recommendation"] \
        == "restrict"


def test_retire_only_at_eighty_percent(store):
    _seed_mixed(store, "quartermaster", n_weak=7, n_strong=3)
    MT.evaluate_reviews(store, OWNER)
    assert MT.open_case_for(store, OWNER, "quartermaster")[
        "recommendation"] == "restrict"
    _seed_mixed(store, "watchman", n_weak=8, n_strong=2)
    MT.evaluate_reviews(store, OWNER)
    assert MT.open_case_for(store, OWNER, "watchman")[
        "recommendation"] == "retire"


def test_no_duplicate_case_while_open(store):
    _seed_mixed(store, "scout", n_weak=3, n_strong=7)
    first = MT.evaluate_reviews(store, OWNER)
    second = MT.evaluate_reviews(store, OWNER)
    assert len(first["cases_opened"]) == 1
    assert second["cases_opened"] == []
    assert len(MT.list_cases(store, OWNER)) == 1


# ---------------------------------------------------------------------------
# Redelegation drafts
# ---------------------------------------------------------------------------
def test_redelegation_draft_names_duties_and_absorbers(store):
    draft = MT.draft_redelegation(store, OWNER, "scout")
    assert "Redelegation draft for scout" in draft
    assert "fetch_url" in draft
    assert "provider_dispatch" in draft
    # verifier's tools overlap both of scout's duties (registry order
    # breaks the tie with watchman)
    assert "verifier" in draft


def test_redelegation_draft_falls_back_to_rowan_jason(store):
    draft = MT.draft_redelegation(store, OWNER, "envoy")
    assert "returns to Rowan/Jason" in draft


def test_redelegation_draft_unknown_specialist(store):
    with pytest.raises(SP.SpecialistNotFound):
        MT.draft_redelegation(store, OWNER, "nope")


# ---------------------------------------------------------------------------
# Decisions: Mentor cannot decide; effects land as status rows
# ---------------------------------------------------------------------------
def _open_train_case(store, specialist="scout"):
    _seed_mixed(store, specialist, n_weak=3, n_strong=7)
    out = MT.evaluate_reviews(store, OWNER)
    return out["cases_opened"][0]


def test_decide_case_refusals(store):
    cid = _open_train_case(store)
    with pytest.raises(MT.MentorError):
        MT.decide_case(store, OWNER, cid, "train", "")
    with pytest.raises(MT.MentorError):
        MT.decide_case(store, OWNER, cid, "train", "mentor")
    with pytest.raises(MT.MentorError):
        MT.decide_case(store, OWNER, cid, "train", " Mentor ")
    with pytest.raises(MT.MentorError):
        MT.decide_case(store, OWNER, 9999, "train", "jason")
    with pytest.raises(MT.MentorError):
        MT.decide_case(store, OWNER, cid, "promote", "jason")
    # still open after all the refusals
    assert MT.open_case_for(store, OWNER, "scout")["id"] == cid


def test_decide_twice_refused(store):
    cid = _open_train_case(store)
    MT.decide_case(store, OWNER, cid, "dismiss", "jason")
    with pytest.raises(MT.MentorError):
        MT.decide_case(store, OWNER, cid, "train", "jason")


def test_train_decision_changes_no_status(store):
    cid = _open_train_case(store)
    MT.decide_case(store, OWNER, cid, "train", "jason")
    assert SP.effective_status(store, OWNER, "scout") == "active"
    assert MT.open_case_for(store, OWNER, "scout") is None


def test_retire_decision_refuses_runs(store):
    _seed_mixed(store, "scout", n_weak=8, n_strong=2)
    out = MT.evaluate_reviews(store, OWNER)
    cid = out["cases_opened"][0]
    MT.decide_case(store, OWNER, cid, "retire", "jason")
    assert SP.effective_status(store, OWNER, "scout") == "retired"
    det = SP.status_details(store, OWNER, "scout")
    assert det["decided_by"] == "jason"
    # the framework refuses the run like a planned specialist —
    # same error family, naming the retirement and the decider
    with pytest.raises(SP.SpecialistNotActive) as ei:
        SP.run_specialist("scout", "q", store=store, owner=OWNER)
    assert "retired by jason" in str(ei.value)


def test_restrict_decision_marks_runs(store):
    cid = _open_train_case(store)
    MT.decide_case(store, OWNER, cid, "restrict", "rowan")
    assert SP.effective_status(store, OWNER, "scout") == "restricted"
    res = SP.run_specialist(
        "scout", "what?", ["http://example.invalid/x"], owner=OWNER,
        transport=_fake_transport(), fetcher=lambda url: "page text",
        store=store)
    row = SP.get_run(store, res.run_id)
    assert row["result"].startswith(SP.RESTRICTED_MARKER)
    # the marker does not change the grade of a clean run
    grades = MT.grade_runs(store, OWNER, limit=1)
    assert grades[0]["grade"] == "strong"


def test_restrict_marks_builder_runs(store, tmp_path):
    SP.set_specialist_status(store, OWNER, "builder", "restricted",
                             "jason", "case 1")
    project = tmp_path / "proj"
    project.mkdir()
    (project / "mod.py").write_text("x = 1\n", encoding="utf-8")
    row = BL.build(
        store, OWNER, "bump x",
        project_dir=str(project), target_relpath="mod.py",
        test_command=[sys.executable, "-c", "pass"],
        transport=lambda provider, prompt: ("x = 2\n",
                                            {"requests": 1.0,
                                             "tokens": 10.0}))
    assert row["status"] == "done"
    assert row["test_tail"].startswith(SP.RESTRICTED_MARKER)


def test_retired_builder_refuses(store, tmp_path):
    SP.set_specialist_status(store, OWNER, "builder", "retired",
                             "rowan", "case 2")
    project = tmp_path / "proj"
    project.mkdir()
    (project / "mod.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SP.SpecialistNotActive) as ei:
        BL.build(
            store, OWNER, "bump x",
            project_dir=str(project), target_relpath="mod.py",
            test_command=[sys.executable, "-c", "pass"],
            transport=lambda provider, prompt: ("x = 2\n",
                                                {"requests": 1.0,
                                                 "tokens": 10.0}))
    assert "retired by rowan" in str(ei.value)


def test_effective_status_defaults_and_validation(store):
    assert SP.effective_status(store, OWNER, "scout") == "active"
    assert SP.status_details(store, OWNER, "scout") is None
    with pytest.raises(SP.SpecialistError):
        SP.set_specialist_status(store, OWNER, "scout", "active", "")
    with pytest.raises(SP.SpecialistNotFound):
        SP.set_specialist_status(store, OWNER, "nope", "active", "jason")
    with pytest.raises(SP.SpecialistError):
        SP.set_specialist_status(store, OWNER, "scout", "fired",
                                 "jason")


# ---------------------------------------------------------------------------
# Rewards throttle: resource pauses while a case is open
# ---------------------------------------------------------------------------
def test_resource_grant_refused_with_open_case(store):
    cid = _open_train_case(store)
    m = _closed_mission(store)
    with pytest.raises(RW.ReviewPaused) as ei:
        RW.grant(store, OWNER, "scout", "resource", 1, "mission", m.id,
                 granted_by="mentor")
    assert str(cid) in str(ei.value)
    assert "fewer future rewards" in str(ei.value)


def test_cosmetic_grant_unaffected_by_open_case(store):
    _open_train_case(store)
    m = _closed_mission(store)
    row = RW.grant(store, OWNER, "scout", "cosmetic", 1, "mission", m.id,
                   granted_by="mentor")
    assert row["tier"] == "cosmetic"
    assert row["status"] == "active"


def test_existing_rows_untouched_by_throttle(store):
    cid = _open_train_case(store)
    m = _closed_mission(store)
    before = [dict(r) for r in RW.list_rewards(store, OWNER)]
    with pytest.raises(RW.ReviewPaused):
        RW.grant(store, OWNER, "scout", "resource", 1, "mission", m.id,
                 granted_by="mentor")
    RW.grant(store, OWNER, "scout", "cosmetic", 1, "mission", m.id,
             granted_by="mentor")
    after = [dict(r) for r in RW.list_rewards(store, OWNER)]
    # every pre-existing row byte-identical; exactly one row added
    assert len(after) == len(before) + 1
    for old in before:
        match = [r for r in after if r["id"] == old["id"]]
        assert match and match[0] == old
    # the case is still open — nothing was auto-resolved
    assert MT.open_case_for(store, OWNER, "scout")["id"] == cid


def test_resource_grant_works_after_dismiss(store):
    cid = _open_train_case(store)
    MT.decide_case(store, OWNER, cid, "dismiss", "jason")
    m = _closed_mission(store)
    row = RW.grant(store, OWNER, "scout", "resource", 1, "mission", m.id,
                   granted_by="mentor")
    assert row["tier"] == "resource"


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------
def _cli(tmp_path, *argv, capsys=None):
    from luna_v2 import cli
    db = str(tmp_path / "cli.db")
    assert cli.main(["--db", db, "--owner", OWNER, *argv]) == 0
    return db


def test_cli_mentor_grades_reviews_decide_status(tmp_path, capsys):
    from luna_v2 import cli
    db = str(tmp_path / "cli.db")
    s = Store(db)
    _seed_mixed(s, "scout", n_weak=3, n_strong=7)
    s.close()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "mentor", "grades"]) == 0
    out = capsys.readouterr().out
    assert "scout" in out and "weak 3" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "mentor", "reviews"]) == 0
    out = capsys.readouterr().out
    assert "cases opened: 1" in out
    assert "rec=train" in out
    assert cli.main(["--db", db, "--owner", OWNER, "mentor", "status",
                     "scout"]) == 0
    assert "scout: active" in capsys.readouterr().out
    assert cli.main(["--db", db, "--owner", OWNER, "mentor", "decide",
                     "1", "--decision", "restrict", "--by", "jason"]) == 0
    out = capsys.readouterr().out
    assert "restrict decided by jason" in out
    assert cli.main(["--db", db, "--owner", OWNER, "mentor", "status",
                     "scout"]) == 0
    out = capsys.readouterr().out
    assert "scout: restricted" in out and "by jason" in out


def test_cli_decide_refuses_mentor(capsys, tmp_path):
    from luna_v2 import cli
    db = str(tmp_path / "cli.db")
    s = Store(db)
    _seed_mixed(s, "scout", n_weak=3, n_strong=7)
    s.close()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "mentor", "reviews"]) == 0
    capsys.readouterr()
    # Mentor cannot decide — the guarded CLI reports the refusal
    assert cli.main(["--db", db, "--owner", OWNER, "mentor", "decide",
                     "1", "--decision", "train", "--by", "mentor"]) != 0
    captured = capsys.readouterr()  # one read: a second read is empty
    out = captured.out + captured.err
    assert "cannot decide" in out or "Mentor recommends" in out
