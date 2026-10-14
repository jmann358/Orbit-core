"""Tests for the Steward: Luna's personal-projects owner.

Proven here:
- Jason-approved-projects-only: create_project with a blank (or
  whitespace-only) approver is refused and writes nothing.
- Past deadlines are refused.
- The ladder tiers sit at the exact documented boundaries
  (deterministic, injected dates only).
- The question lifecycle: add -> answer / drop.
- Nudge-due math per tier (asked yesterday counts in weekly, not in
  setup), nudge filing updates asked_count/last_asked_at only when a
  nudge is actually filed, and filing is deduped (two checks -> one
  open suggestion).
- Steward ticks make zero provider calls: the broker's usage counters
  are byte-identical before and after a nudge sweep.
- Conductor's project_tick builtin runs the same loop.
- CLI smoke: projects/new/questions/ladder/nudges.
"""
import os
import tempfile
from datetime import date

import pytest

from luna_v2.store import Store
from luna_v2 import conductor as C
from luna_v2 import conductor as CO
from luna_v2 import guardian as GD
from luna_v2 import steward as ST

OWNER = "jason"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _project(s, title="test project", deadline="2026-12-25",
             approved_by="jason", today=date(2026, 10, 14)):
    return ST.create_project(s, OWNER, title, deadline,
                             approved_by=approved_by, today=today)


# -- hard boundaries ------------------------------------------------------

def test_create_refuses_blank_approver(store):
    for bad in ("", "   "):
        with pytest.raises(ST.StewardError):
            ST.create_project(store, OWNER, "x", "2026-12-25",
                              approved_by=bad)
    assert ST.list_projects(store, OWNER) == []


def test_create_refuses_blank_title(store):
    with pytest.raises(ST.StewardError):
        ST.create_project(store, OWNER, "  ", "2026-12-25",
                          approved_by="jason")
    assert ST.list_projects(store, OWNER) == []


def test_create_refuses_past_deadline(store):
    with pytest.raises(ST.StewardError):
        ST.create_project(store, OWNER, "late", "2026-10-13",
                          approved_by="jason", today=date(2026, 10, 14))
    assert ST.list_projects(store, OWNER) == []


def test_create_refuses_bad_date(store):
    with pytest.raises(ST.StewardError):
        ST.create_project(store, OWNER, "x", "next friday",
                          approved_by="jason")


# -- the ladder -----------------------------------------------------------

def test_ladder_tier_boundaries(store):
    deadline = date(2026, 12, 25)
    cases = [
        # (today, expected tier, expected days_left)
        (date(2026, 10, 14), "setup", 72),        # Christmas mission, live
        (date(2026, 11, 9), "setup", 46),
        (date(2026, 11, 10), "weekly", 45),       # edge
        (date(2026, 12, 10), "weekly", 15),       # edge
        (date(2026, 12, 11), "twice_weekly", 14),  # edge
        (date(2026, 12, 17), "twice_weekly", 8),  # edge
        (date(2026, 12, 18), "daily", 7),         # edge
        (date(2026, 12, 24), "daily", 1),         # edge
        (date(2026, 12, 25), "final", 0),         # edge: the day itself
        (date(2026, 12, 26), "closed_window", -1),
    ]
    for today, want_tier, want_left in cases:
        p = ST.create_project(store, OWNER, f"p-{want_tier}",
                              deadline.isoformat(), approved_by="jason",
                              today=min(today, date(2026, 10, 14)))
        got = ST.ladder_status(p, today=today)
        assert got["tier"] == want_tier, (today, got)
        assert got["days_left"] == want_left
        if want_tier != "closed_window":
            assert got["nudge_gap_days"] is not None
        else:
            assert got["nudge_gap_days"] is None


# -- the question queue ---------------------------------------------------

def test_question_lifecycle(store):
    p = _project(store)
    q = ST.add_question(store, OWNER, p["id"], "Who is on the list?")
    assert q["status"] == "open" and q["asked_count"] == 0
    answered = ST.answer_question(store, OWNER, q["id"], "sister, brother")
    assert answered["status"] == "answered"
    assert answered["answer_note"] == "sister, brother"
    assert ST.list_questions(store, OWNER, p["id"], "open") == []
    q2 = ST.add_question(store, OWNER, p["id"], "budget?")
    ST.drop_question(store, OWNER, q2["id"])
    assert ST.list_questions(store, OWNER, p["id"], "open") == []


def test_blank_question_and_answer_refused(store):
    p = _project(store)
    with pytest.raises(ST.StewardError):
        ST.add_question(store, OWNER, p["id"], "   ")
    q = ST.add_question(store, OWNER, p["id"], "real question")
    with pytest.raises(ST.StewardError):
        ST.answer_question(store, OWNER, q["id"], "  ")


def test_unknown_project_and_question(store):
    with pytest.raises(ST.StewardError):
        ST.add_question(store, OWNER, 999, "q?")
    with pytest.raises(ST.StewardError):
        ST.answer_question(store, OWNER, 999, "a")
    with pytest.raises(ST.StewardError):
        ST.drop_question(store, OWNER, 999)
    with pytest.raises(ST.StewardError):
        ST.get_project(store, OWNER, 999)


# -- nudge due math --------------------------------------------------------

def test_never_asked_is_always_due(store):
    p = _project(store, deadline="2027-06-01")  # setup tier
    ST.add_question(store, OWNER, p["id"], "never asked")
    _, due = ST.due_questions(store, OWNER, p["id"], date(2026, 10, 14))
    assert len(due) == 1


def test_due_math_per_tier(store):
    # Asked yesterday: due again in daily (gap 1), not in weekly (gap 7).
    daily = ST.create_project(store, OWNER, "daily", "2026-12-20",
                              approved_by="jason",
                              today=date(2026, 10, 14))
    ST.add_question(store, OWNER, daily["id"], "q1")
    _, due = ST.due_questions(store, OWNER, daily["id"], date(2026, 12, 18))
    assert len(due) == 1
    # simulate an ask on 2026-12-17
    store._db.execute(
        "UPDATE project_questions SET asked_count = 1, last_asked_at = ?",
        ("2026-12-17",))
    store._db.commit()
    _, due = ST.due_questions(store, OWNER, daily["id"], date(2026, 12, 18))
    assert len(due) == 1  # daily: yesterday is >= 1 day ago

    weekly = ST.create_project(store, OWNER, "weekly", "2026-12-20",
                               approved_by="jason",
                               today=date(2026, 10, 14))
    ST.add_question(store, OWNER, weekly["id"], "q1")
    store._db.execute(
        "UPDATE project_questions SET asked_count = 1, last_asked_at = ? "
        "WHERE project_id = ?",
        ("2026-11-25", weekly["id"]))
    store._db.commit()
    _, due = ST.due_questions(store, OWNER, weekly["id"], date(2026, 11, 26))
    assert len(due) == 0  # weekly: 1 day < 7-day gap
    _, due = ST.due_questions(store, OWNER, weekly["id"], date(2026, 12, 2))
    assert len(due) == 1  # weekly: 7 days >= 7-day gap


def test_answered_questions_are_never_due(store):
    p = _project(store)
    q = ST.add_question(store, OWNER, p["id"], "answered one")
    ST.answer_question(store, OWNER, q["id"], "done")
    _, due = ST.due_questions(store, OWNER, p["id"], date(2026, 10, 14))
    assert due == []


# -- the nudge loop --------------------------------------------------------

def test_nudge_check_files_one_deduped_suggestion(store):
    p = _project(store)
    ST.add_question(store, OWNER, p["id"], "Who is on the list?")
    res1 = ST.nudge_check(store, OWNER, date(2026, 10, 14))
    assert res1["active_projects"] == 1
    assert res1["nudged_projects"] == 1
    assert res1["suggestions_filed"] == 1
    rows = GD.inbox(store, OWNER)
    assert any(r["check_name"] == "steward_nudge" for r in rows)
    suggestion = next(r for r in rows if r["check_name"] == "steward_nudge")
    assert p["title"] in suggestion["observation"]
    assert "setup" in suggestion["observation"]
    assert suggestion["severity"] == "info"

    # Second check: no new suggestion (dedupe), and the question was
    # re-asked today so nothing is due again either.
    res2 = ST.nudge_check(store, OWNER, date(2026, 10, 14))
    assert res2["suggestions_filed"] == 0
    assert res2["nudged_projects"] == 0
    assert len(GD.inbox(store, OWNER)) == 1


def test_nudge_updates_counters_only_when_filed(store):
    p = _project(store)
    q = ST.add_question(store, OWNER, p["id"], "q")
    res = ST.nudge_check(store, OWNER, date(2026, 10, 14))
    assert res["suggestions_filed"] == 1
    row = store._db.execute(
        "SELECT * FROM project_questions WHERE id = ?", (q["id"],)).fetchone()
    assert row["asked_count"] == 1
    assert row["last_asked_at"] == "2026-10-14"
    # Close the open suggestion, re-run 31 days later (setup tier's 30-day
    # gap is satisfied): the question is due again, a new suggestion files,
    # and the counters bump.
    store._db.execute(
        "UPDATE guardian_suggestions SET status = 'done'")
    store._db.commit()
    res2 = ST.nudge_check(store, OWNER, date(2026, 11, 14))
    assert res2["suggestions_filed"] == 1
    row = store._db.execute(
        "SELECT * FROM project_questions WHERE id = ?", (q["id"],)).fetchone()
    assert row["asked_count"] == 2
    assert row["last_asked_at"] == "2026-11-14"


def test_nudge_check_quiet_when_nothing_due(store):
    _project(store)  # no questions at all
    res = ST.nudge_check(store, OWNER, date(2026, 10, 14))
    assert res["suggestions_filed"] == 0
    assert GD.inbox(store, OWNER) == []


def test_closed_window_tier_never_nudges(store):
    p = ST.create_project(store, OWNER, "past", "2026-12-25",
                          approved_by="jason", today=date(2026, 10, 14))
    ST.add_question(store, OWNER, p["id"], "too late?")
    res = ST.nudge_check(store, OWNER, date(2026, 12, 30))
    assert res["suggestions_filed"] == 0


def test_handoff_and_status(store):
    p = _project(store)
    ST.set_handoff(store, OWNER, p["id"],
                   "Conductor + Herald + Scout + Quartermaster")
    assert ST.get_project(store, OWNER, p["id"])["handoff"].startswith(
        "Conductor")
    ST.set_status(store, OWNER, p["id"], "done")
    assert ST.get_project(store, OWNER, p["id"])["status"] == "done"
    with pytest.raises(ST.StewardError):
        ST.set_status(store, OWNER, p["id"], "gone")


# -- zero provider calls ---------------------------------------------------

def test_steward_tick_makes_zero_provider_calls(store):
    def _ledger():
        return store._db.execute(
            "SELECT * FROM broker_usage WHERE owner = ?", (OWNER,)
        ).fetchall()

    p = _project(store)
    ST.add_question(store, OWNER, p["id"], "q")
    before = _ledger()
    ST.nudge_check(store, OWNER, date(2026, 10, 14))
    ST.ladder_status(p, date(2026, 10, 14))
    assert _ledger() == before


# -- conductor integration ---------------------------------------------------

def test_conductor_project_tick_runs_nudge_loop(store):
    p = _project(store)
    ST.add_question(store, OWNER, p["id"], "q")
    runner, natural = C.BUILTIN_RUNNERS["project_tick"]
    assert natural == "steward"
    out = runner(store, OWNER)
    assert "1 project(s) with due questions" in out
    rows = GD.inbox(store, OWNER)
    assert any(r["check_name"] == "steward_nudge" for r in rows)


def test_conductor_accepts_project_tick_backlog(store):
    CO.add_backlog(store, OWNER, "nudge sweep", "project_tick")
    item = store._db.execute(
        "SELECT * FROM work_backlog WHERE kind = 'project_tick'"
    ).fetchone()
    assert item is not None


# -- CLI smoke ---------------------------------------------------------------

def test_cli_steward_round_trip(tmp_path, capsys):
    from luna_v2 import cli
    db = str(tmp_path / "steward-cli.db")

    def run(*argv):
        assert cli.main(["--db", db, "--owner", OWNER, *argv]) == 0

    run("steward", "projects")
    run("steward", "new", "--title", "Christmas List 2026",
        "--deadline", "2026-12-25", "--approved-by", "jason")
    run("steward", "questions", "--project", "1")
    run("steward", "question", "add", "--project", "1", "--text",
        "Who is on the list?")
    run("steward", "question", "answer", "--id", "1", "--answer", "sister")
    run("steward", "question", "add", "--project", "1", "--text", "budget?")
    run("steward", "question", "drop", "--id", "2")
    run("steward", "ladder", "--project", "1")
    run("steward", "nudges")
    out = capsys.readouterr().out
    assert "Christmas List 2026" in out
    assert "question 1 queued" in out
    assert "question 2 dropped" in out
