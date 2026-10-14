"""Tests for Scheduler: recurring-mission templates + tick().

Every test runs against a throwaway SQLite file; no network anywhere.
Scheduler makes zero provider calls and writes only its own schedules
table; missions go through the missions API, so consequential guards
still bite.
"""
from datetime import datetime, timedelta, timezone

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import scheduler as S


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "sched.db"))
    yield s
    s.close()


def _utc(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(
        timespec="seconds")


def _mission_steps(store, mission_id):
    return store.list_steps(mission_id)


def _template():
    return [
        {"description": "check the burn rates", "kind": "routine"},
        {"description": "approve the reallocation", "kind": "consequential"},
    ]


# -- core tick behavior ------------------------------------------------------
def test_due_daily_schedule_fires_once_with_template_steps(store):
    # Explicit timestamps keep the "second tick fires nothing" check
    # deterministic: the first tick lands mid-period, so the advanced
    # next_run_at is genuinely in the future relative to tick time.
    start = "2026-10-10T12:00:00+00:00"
    tick_time = "2026-10-10T18:00:00+00:00"
    sid = S.create_schedule(store, "jason", "morning-check",
                            "Morning check-in", _template(), "daily",
                            start_at=start)
    fired = S.tick(store, "jason", now=tick_time)
    assert fired and len(fired) == 1
    assert fired[0][0] == sid

    mission = M._mission_or_raise(store, fired[0][1])
    assert "morning-check" in mission["outcome"]
    assert "daily" in mission["outcome"]
    steps = _mission_steps(store, mission["id"])
    assert [s["description"] for s in steps] == [
        "check the burn rates", "approve the reallocation"]
    assert [s["kind"] for s in steps] == ["routine", "consequential"]
    assert all(s["status"] == "open" for s in steps)

    sched = S.get_schedule(store, "jason", sid)
    expected_next = "2026-10-11T12:00:00+00:00"
    assert sched["next_run_at"] == expected_next
    assert sched["last_mission_id"] == mission["id"]
    assert sched["last_run_at"] == tick_time

    # An immediate second tick fires nothing: next run is tomorrow.
    assert S.tick(store, "jason", now=tick_time) == []
    assert len(S.list_schedules(store, "jason")) == 1  # schedule itself intact


def test_weekly_cadence_advances_seven_days(store):
    start = _utc()
    sid = S.create_schedule(store, "jason", "weekly-review",
                            "Weekly review",
                            [{"description": "read the ledger",
                              "kind": "routine"}],
                            "weekly", start_at=start)
    assert S.tick(store, "jason", now=_utc()) != []
    sched = S.get_schedule(store, "jason", sid)
    expected = (datetime.fromisoformat(start)
                + timedelta(days=7)).isoformat(timespec="seconds")
    assert sched["next_run_at"] == expected


def test_future_schedule_untouched(store):
    sid = S.create_schedule(store, "jason", "future-thing",
                            "Future thing",
                            [{"description": "wait", "kind": "routine"}],
                            "daily", start_at=_utc(days_ago=-2))
    before = S.get_schedule(store, "jason", sid)["next_run_at"]
    assert S.tick(store, "jason", now=_utc()) == []
    after = S.get_schedule(store, "jason", sid)
    assert after["next_run_at"] == before
    assert after["last_mission_id"] is None
    assert len(S.list_schedules(store, "jason")) == 1


def test_inactive_schedule_skipped_even_when_past_due(store):
    sid = S.create_schedule(store, "jason", "paused",
                            "Paused routine",
                            [{"description": "nap", "kind": "routine"}],
                            "daily", start_at=_utc(days_ago=5))
    S.set_active(store, "jason", sid, False)
    assert S.tick(store, "jason", now=_utc()) == []
    sched = S.get_schedule(store, "jason", sid)
    assert sched["active"] == 0
    assert sched["last_mission_id"] is None
    # ... and no mission row was created at all
    assert store._db.execute("SELECT COUNT(*) c FROM missions").fetchone()["c"] == 0


def test_three_periods_behind_creates_one_mission_no_burst(store):
    start = _utc(days_ago=3)
    sid = S.create_schedule(store, "jason", "catchup",
                            "Catch-up routine",
                            [{"description": "one thing", "kind": "routine"}],
                            "daily", start_at=start)
    fired = S.tick(store, "jason", now=_utc())
    assert len(fired) == 1  # exactly one mission, not three
    sched = S.get_schedule(store, "jason", sid)
    expected = (datetime.fromisoformat(start)
                + timedelta(days=1)).isoformat(timespec="seconds")
    assert sched["next_run_at"] == expected  # one period of catch-up


def test_implicit_start_at_is_due_immediately(store):
    sid = S.create_schedule(store, "jason", "now-thing", "Now thing",
                            [{"description": "go", "kind": "routine"}],
                            "daily")
    fired = S.tick(store, "jason")
    assert len(fired) == 1 and fired[0][0] == sid


def test_consequential_template_step_awaits_approval(store):
    sid = S.create_schedule(store, "jason", "risky-routine",
                            "Risky routine", _template(), "daily",
                            start_at=_utc())
    fired = S.tick(store, "jason", now=_utc())
    step_rows = _mission_steps(store, fired[0][1])
    conseq = [s for s in step_rows if s["kind"] == "consequential"][0]
    # It is still open and NOT pre-approved: the approval gate holds.
    assert conseq["status"] == "open"
    assert M.is_approved(store, conseq) is False
    with pytest.raises(M.StepNotApproved):
        M.complete_step(store, conseq["id"], "did it", "proof")


# -- validation --------------------------------------------------------------
def test_bad_cadence_refused(store):
    with pytest.raises(S.SchedulerError):
        S.create_schedule(store, "jason", "x", "X",
                          [{"description": "y", "kind": "routine"}],
                          "hourly")


def test_bad_step_kind_refused(store):
    with pytest.raises(S.SchedulerError):
        S.create_schedule(store, "jason", "x", "X",
                          [{"description": "y", "kind": "wild"}],
                          "daily")


def test_empty_steps_refused(store):
    with pytest.raises(S.SchedulerError):
        S.create_schedule(store, "jason", "x", "X", [], "daily")


def test_blank_step_description_refused(store):
    with pytest.raises(S.SchedulerError):
        S.create_schedule(store, "jason", "x", "X",
                          [{"description": "   ", "kind": "routine"}],
                          "daily")


def test_duplicate_active_name_refused(store):
    steps = [{"description": "y", "kind": "routine"}]
    S.create_schedule(store, "jason", "same-name", "First", steps, "daily")
    with pytest.raises(S.SchedulerError):
        S.create_schedule(store, "jason", "same-name", "Second", steps, "daily")
    # An inactive schedule's name is reusable — deactivating clears it.
    sid = S.create_schedule(store, "jason", "old-name", "Old", steps, "daily")
    S.set_active(store, "jason", sid, False)
    S.create_schedule(store, "jason", "old-name", "New", steps, "daily")
    # ... but re-activating the old one now would clash: refused.
    with pytest.raises(S.SchedulerError):
        S.set_active(store, "jason", sid, True)


def test_set_active_missing_id(store):
    with pytest.raises(S.ScheduleNotFound):
        S.set_active(store, "jason", 999, False)


def test_set_active_other_owners_schedule_is_invisible(store):
    steps = [{"description": "y", "kind": "routine"}]
    sid = S.create_schedule(store, "jason", "mine", "Mine", steps, "daily")
    with pytest.raises(S.ScheduleNotFound):
        S.set_active(store, "friend", sid, False)


# -- owner isolation ----------------------------------------------------------
def test_tick_does_not_fire_another_owners_schedules(store):
    steps = [{"description": "y", "kind": "routine"}]
    sid = S.create_schedule(store, "jason", "jason-routine",
                            "Jason routine", steps, "daily",
                            start_at=_utc(days_ago=1))
    before = S.get_schedule(store, "jason", sid)["next_run_at"]
    assert S.tick(store, "friend", now=_utc()) == []
    after = S.get_schedule(store, "jason", sid)
    assert after["next_run_at"] == before
    assert after["last_mission_id"] is None
    assert S.list_schedules(store, "friend") == []
    assert len(S.list_schedules(store, "jason")) == 1


def test_start_at_accepts_datetime_object(store):
    dt = datetime.now(timezone.utc) - timedelta(hours=1)
    sid = S.create_schedule(store, "jason", "dt-start", "DT start",
                            [{"description": "go", "kind": "routine"}],
                            "daily", start_at=dt)
    fired = S.tick(store, "jason")
    assert len(fired) == 1 and fired[0][0] == sid
