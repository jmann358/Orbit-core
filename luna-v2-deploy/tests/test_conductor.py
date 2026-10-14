"""Tests for the Conductor: the anti-idle coordinator.

Conductor watches idleness, keeps a backlog of useful routine work, and
assigns it to the most idle ELIGIBLE specialist. It never invents
busywork: retired agents get nothing, restricted agents get training
only, and an empty backlog (or no eligible specialist) means zero
assignments, stated plainly.
"""
import os
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from luna_v2.store import Store
from luna_v2 import conductor as CO
from luna_v2 import specialists as SP
from luna_v2 import missions as MS

OWNER = "jason"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _stamp_run(s, specialist, age_days=0):
    SP._ensure_schema(s)
    ts = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat(
        timespec="seconds")
    s._db.execute(
        "INSERT INTO specialist_runs (specialist, owner, created_at) "
        "VALUES (?, ?, ?)", (specialist, OWNER, ts))
    s._db.commit()


def _retire_all_but(s, keep):
    for name in SP.SPECIALISTS:
        if name != keep and name != "conductor":
            SP.set_specialist_status(s, OWNER, name, "retired", "jason",
                                     "test isolation")


def _now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Idleness
# ---------------------------------------------------------------------------
def test_idleness_ranks_never_ran_first(store):
    _stamp_run(store, "scout", age_days=0)
    board = CO.idleness(store, OWNER)
    assert len(board) == 32
    first = board[0]
    assert first["days_idle"] is None  # never ran: most idle
    scout = next(r for r in board if r["specialist"] == "scout")
    assert scout["days_idle"] is not None
    assert scout["days_idle"] < 1.0
    # Never-ran sorts strictly before any ran agent
    assert board.index(first) < board.index(scout)


def test_idleness_reports_effective_status(store):
    SP.set_specialist_status(store, OWNER, "host", "retired", "jason",
                             "test")
    board = CO.idleness(store, OWNER)
    host = next(r for r in board if r["specialist"] == "host")
    assert host["effective_status"] == "retired"


# ---------------------------------------------------------------------------
# Backlog basics
# ---------------------------------------------------------------------------
def test_backlog_add_list_round_trip(store):
    CO.add_backlog(store, OWNER, "low pri tidy", "tidy", priority=8)
    CO.add_backlog(store, OWNER, "high pri check", "health_check",
                   priority=1)
    rows = CO.list_backlog(store, OWNER)
    assert [r["title"] for r in rows] == ["high pri check", "low pri tidy"]
    assert rows[0]["status"] == "open"


def test_backlog_add_idempotent_on_title(store):
    a = CO.add_backlog(store, OWNER, "same job", "tidy", priority=9)
    b = CO.add_backlog(store, OWNER, "same job", "tidy", priority=1)
    assert a == b
    rows = CO.list_backlog(store, OWNER)
    assert len(rows) == 1
    assert rows[0]["priority"] == 1  # updated, not duplicated


def test_backlog_refuses_unknown_kind(store):
    with pytest.raises(CO.ConductorError):
        CO.add_backlog(store, OWNER, "bogus", "nap_time")


def test_backlog_refuses_unknown_target(store):
    with pytest.raises(Exception):
        CO.add_backlog(store, OWNER, "bogus", "tidy",
                       target_specialist="nobody")


def test_seed_is_idempotent(store):
    first = CO.seed_backlog(store, OWNER)
    second = CO.seed_backlog(store, OWNER)
    assert len(first) == 6
    assert sorted(first) == sorted(second)
    assert len(CO.list_backlog(store, OWNER)) == 6


# ---------------------------------------------------------------------------
# Tick: the empty cases
# ---------------------------------------------------------------------------
def test_tick_empty_backlog_assigns_zero_and_says_so(store):
    out = CO.tick(store, OWNER)
    assert out["assigned"] == []
    assert out["skipped"] == []
    assert "empty" in out["note"]


def test_tick_no_eligible_specialist_assigns_zero(store):
    for name in SP.SPECIALISTS:
        if name != "conductor":
            SP.set_specialist_status(store, OWNER, name, "retired",
                                     "jason", "test")
    CO.add_backlog(store, OWNER, "retire-able check", "health_check")
    out = CO.tick(store, OWNER)
    assert out["assigned"] == []
    assert "no eligible specialist" in out["note"]


def test_daily_cap_enforced(store):
    bids = [CO.add_backlog(store, OWNER, f"cap job {i}", "tidy")
            for i in range(CO.DAILY_CAP)]
    for bid in bids:
        store._db.execute(
            "INSERT INTO assignments (owner, backlog_id, specialist, "
            "how, outcome, assigned_at) VALUES (?, ?, ?, ?, ?, ?)",
            (OWNER, bid, "scout", "builtin", "ok", _now_utc()))
    store._db.commit()
    CO.add_backlog(store, OWNER, "extra work", "tidy")
    out = CO.tick(store, OWNER)
    assert out["assigned"] == []
    assert "daily cap" in out["note"]


# ---------------------------------------------------------------------------
# Tick: built-ins execute on the natural owner
# ---------------------------------------------------------------------------
def test_tick_builtin_executes_and_logs_outcome(store):
    CO.add_backlog(store, OWNER, "health sweep", "health_check")
    out = CO.tick(store, OWNER)
    assert len(out["assigned"]) == 1
    a = out["assigned"][0]
    assert a["specialist"] == "watchman"  # natural owner for health_check
    assert a["how"] == "builtin"
    assert a["outcome"].startswith("ok: health ")
    items = CO.list_backlog(store, OWNER, status="done")
    assert len(items) == 1
    rows = CO.recent_assignments(store, OWNER)
    assert len(rows) == 1
    assert rows[0]["how"] == "builtin"


def test_tick_builtin_failure_recorded_honestly(store):
    # A broken module should produce an error outcome, not an exception.
    import luna_v2.conductor as C
    orig = C.BUILTIN_RUNNERS["health_check"]
    C.BUILTIN_RUNNERS["health_check"] = (
        lambda s, o: (_ for _ in ()).throw(RuntimeError("boom")), "watchman")
    try:
        CO.add_backlog(store, OWNER, "doomed sweep", "health_check")
        out = CO.tick(store, OWNER)
        assert out["assigned"][0]["outcome"] == "error: boom"
        rows = CO.recent_assignments(store, OWNER)
        assert rows[0]["outcome"] == "error: boom"
    finally:
        C.BUILTIN_RUNNERS["health_check"] = orig


def test_builtin_maps_to_natural_owner(store):
    assert CO.most_idle(store, OWNER, "qm_report",
                        target=CO.BUILTIN_OWNER["qm_report"]
                        )["specialist"] == "quartermaster"


# ---------------------------------------------------------------------------
# Tick: mission kinds create real routine missions
# ---------------------------------------------------------------------------
def test_mission_kind_creates_real_routine_mission(store):
    _retire_all_but(store, "scout")
    CO.add_backlog(store, OWNER, "practice research", "training")
    out = CO.tick(store, OWNER)
    assert len(out["assigned"]) == 1
    a = out["assigned"][0]
    assert a["specialist"] == "scout"
    assert a["how"] == "mission"
    mission = store.get_mission(int(
        CO.recent_assignments(store, OWNER)[0]["mission_id"]))
    assert mission is not None
    assert mission["owner"] == OWNER
    assert "Conductor" in mission["title"]
    steps = store.list_steps(mission["id"])
    assert len(steps) == 3
    assert all(s["kind"] == "routine" for s in steps)
    items = CO.list_backlog(store, OWNER, status="assigned")
    assert len(items) == 1


# ---------------------------------------------------------------------------
# Retirement and restriction rules
# ---------------------------------------------------------------------------
def test_retired_specialist_excluded_even_when_most_idle(store):
    # Host is retired but would otherwise be most idle; a health_check
    # item must NOT go to it (and with everyone else retired, to no one).
    _retire_all_but(store, "host")
    SP.set_specialist_status(store, OWNER, "host", "retired", "jason",
                             "test")
    CO.add_backlog(store, OWNER, "host health", "health_check",
                   target_specialist="host")
    out = CO.tick(store, OWNER)
    assert out["assigned"] == []
    assert len(out["skipped"]) == 1
    assert CO.recent_assignments(store, OWNER) == []


def test_restricted_gets_training_but_not_research(store):
    _retire_all_but(store, "registrar")
    SP.set_specialist_status(store, OWNER, "registrar", "restricted",
                             "jason", "test")
    CO.add_backlog(store, OWNER, "a research job", "research")
    out = CO.tick(store, OWNER)
    assert out["assigned"] == []  # restricted can't take research
    CO.add_backlog(store, OWNER, "a training drill", "training")
    out = CO.tick(store, OWNER)
    assert len(out["assigned"]) == 1
    assert out["assigned"][0]["specialist"] == "registrar"
    assert out["assigned"][0]["how"] == "mission"


def test_tick_respects_explicit_target(store):
    _retire_all_but(store, "scout")
    CO.add_backlog(store, OWNER, "scout research", "research",
                   target_specialist="scout")
    out = CO.tick(store, OWNER)
    assert out["assigned"][0]["specialist"] == "scout"


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------
def test_tick_takes_highest_priority_first(store):
    CO.add_backlog(store, OWNER, "later job", "tidy", priority=9)
    CO.add_backlog(store, OWNER, "sooner job", "tidy", priority=1)
    out = CO.tick(store, OWNER, max_assignments=1)
    assert len(out["assigned"]) == 1
    assert out["assigned"][0]["title"] == "sooner job"
