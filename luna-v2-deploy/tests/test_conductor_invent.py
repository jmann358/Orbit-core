"""Tests for the Conductor's invention charter (Jason, 2026-10-14).

Conductor may invent work — but only if it is productive enough to be
worth it. Invention is state-driven, every invented item carries a
mandatory one-sentence value_case, invented items queue behind standing
work, at most 2 may be open at once, a tick assigns at most 1, and the
same pattern+target never re-invents within 7 days.
"""
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from luna_v2.store import Store
from luna_v2 import conductor as CO
from luna_v2 import specialists as SP
from luna_v2 import missions as MS
from luna_v2 import broker as B
from luna_v2 import mentor as MT
from luna_v2 import verifier as V

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


def _stamp_all_runs(s):
    for p in SP.list_specialists():
        if p.name != "conductor":
            _stamp_run(s, p.name)


def _closed_mission(s, title):
    m = MS.create_mission(s, OWNER, title=title, outcome="test outcome")
    st = MS.add_step(s, OWNER, m.id, "do the thing", kind=MS.ROUTINE)
    MS.complete_step(s, st.id, "done", evidence="proof")
    MS.close_mission(s, m.id)
    return m.id


def _clean_state(s):
    """A workshop DB with nothing worth inventing: all specialists ran,
    runs graded, one verified mission, no hot allocations."""
    _stamp_all_runs(s)
    MT.persist_grades(s, OWNER)
    mid = _closed_mission(s, "verified job")
    V.verify_mission(s, mid, owner=OWNER)
    return mid


def _today_str():
    return datetime.now(timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# Worth-it enforcement at insert
# ---------------------------------------------------------------------------
def test_invented_without_value_case_refused(store):
    with pytest.raises(CO.ConductorError):
        CO.add_backlog(store, OWNER, "vague invention", "tidy",
                       origin="invented", value_case="")
    with pytest.raises(CO.ConductorError):
        CO.add_backlog(store, OWNER, "vague invention", "tidy",
                       origin="invented", value_case="   ")


def test_invented_with_value_case_accepted(store):
    bid = CO.add_backlog(store, OWNER, "worthwhile invention", "tidy",
                         origin="invented",
                         value_case="Saves a real hour a week, concretely.")
    row = CO.list_backlog(store, OWNER)[0]
    assert row["id"] == bid
    assert row["origin"] == "invented"
    assert row["value_case"].startswith("Saves a real hour")


def test_unknown_origin_refused(store):
    with pytest.raises(CO.ConductorError):
        CO.add_backlog(store, OWNER, "mystery", "tidy", origin="boss")


def test_non_invented_origins_need_no_value_case(store):
    for origin in ("standing", "jason", "rowan"):
        CO.add_backlog(store, OWNER, f"job from {origin}", "tidy",
                       origin=origin)
    assert len(CO.list_backlog(store, OWNER)) == 3


# ---------------------------------------------------------------------------
# Pattern (a): stale verification
# ---------------------------------------------------------------------------
def test_invent_fires_on_stale_receipt(store):
    _clean_state(store)
    m1 = _closed_mission(store, "stale one")
    m2 = _closed_mission(store, "stale two")
    # m1 and m2 are newer than the verified fixture mission; oldest stale
    # is the fixture one, but it has a verify run — so m1 must win.
    out = CO.invent_work(store, OWNER, limit=1)
    assert len(out["invented"]) == 1
    inv = out["invented"][0]
    assert inv["pattern"] == "stale-verification"
    assert inv["kind"] == "verify_recent"
    assert inv["target"] == "verifier"
    assert f"mission {m1}" in inv["title"]
    assert inv["value_case"].strip()  # worth-it case is mandatory
    payload = json.loads(
        CO.list_backlog(store, OWNER)[0]["payload"])
    assert payload["mission_id"] == m1
    assert _today_str() in inv["title"]  # date-stamped for re-invention


def test_invent_stops_when_everything_verified(store):
    _clean_state(store)
    out = CO.invent_work(store, OWNER)
    assert out["invented"] == []
    assert "nothing worth inventing" in out["note"]
    reasons = {sk["pattern"]: sk["reason"] for sk in out["skipped"]}
    assert "stale-verification" in reasons


# ---------------------------------------------------------------------------
# Pattern (b): allocation risk
# ---------------------------------------------------------------------------
def test_invent_fires_on_burning_allocation(store):
    _clean_state(store)
    B.seed_providers(store, OWNER)
    # Cloudflare: 10,000 neurons/day — burn 90% of it (first in list order,
    # so the burn variant wins deterministically).
    B.record_usage(store, OWNER, "cloudflare", "neurons", 9000.0)
    out = CO.invent_work(store, OWNER, limit=1)
    inv = out["invented"][0]
    assert inv["pattern"] == "allocation-risk"
    assert inv["kind"] == "research"
    assert inv["target"] == "scout"
    assert "cloudflare" in inv["value_case"]
    assert "90%" in inv["value_case"]


def test_invent_fires_on_use_or_lose_allocation(store):
    _clean_state(store)
    B.seed_providers(store, OWNER)
    # Gemini tokens: unknown-quota providers never route, but groq tokens
    # are 200k/day — burn 1% so it reads "resets soon, barely used".
    B.record_usage(store, OWNER, "groq", "tokens", 1000.0)
    out = CO.invent_work(store, OWNER, limit=1)
    patterns = {i["pattern"] for i in out["invented"]}
    assert "allocation-risk" in patterns
    inv = out["invented"][0]
    assert "use" in inv["value_case"].lower() or "%" in inv["value_case"]


# ---------------------------------------------------------------------------
# Pattern (c): grade gap
# ---------------------------------------------------------------------------
def test_invent_fires_on_grade_gap(store):
    _clean_state(store)
    _stamp_run(store, "scout")  # a fresh run, but grades were persisted
    # Wipe scout's grade so the run sits ungraded.
    store._db.execute(
        "DELETE FROM mentor_grades WHERE owner = ? AND specialist = ?",
        (OWNER, "scout"))
    store._db.commit()
    out = CO.invent_work(store, OWNER, limit=1)
    patterns = {i["pattern"] for i in out["invented"]}
    assert "grade-gap" in patterns
    inv = out["invented"][0]
    assert inv["kind"] == "mentor_grades"
    assert "scout" in inv["value_case"]


# ---------------------------------------------------------------------------
# Pattern (d): rotation gap
# ---------------------------------------------------------------------------
def test_invent_fires_on_rotation_gap(store):
    _clean_state(store)
    # Idleness counts Mentor grades as activity, so a true rotation gap
    # needs NO runs AND no grades for the specialist.
    store._db.execute(
        "DELETE FROM specialist_runs WHERE owner = ? AND specialist = ?",
        (OWNER, "armorer"))
    store._db.execute(
        "DELETE FROM mentor_grades WHERE owner = ? AND specialist = ?",
        (OWNER, "armorer"))
    store._db.commit()
    out = CO.invent_work(store, OWNER, limit=1)
    patterns = {i["pattern"] for i in out["invented"]}
    assert "rotation-gap" in patterns
    inv = out["invented"][0]
    assert inv["target"] == "armorer"
    assert inv["kind"] == "training"
    assert "armorer" in inv["value_case"]


# ---------------------------------------------------------------------------
# Discipline: queue position, caps, dedupe
# ---------------------------------------------------------------------------
def test_invented_priority_never_beats_standing(store):
    _clean_state(store)
    CO.seed_backlog(store, OWNER)  # standing priorities 2..6
    m = _closed_mission(store, "stale job")
    out = CO.invent_work(store, OWNER, limit=1)
    assert len(out["invented"]) == 1
    row = CO.list_backlog(store, OWNER)[-1]
    assert row["origin"] == "invented"
    assert row["priority"] == 6  # worst standing priority


def test_invented_priority_defaults_sane_with_no_standing(store):
    _clean_state(store)
    _closed_mission(store, "stale job")
    out = CO.invent_work(store, OWNER, limit=1)
    row = CO.list_backlog(store, OWNER)[0]
    assert row["origin"] == "invented"
    assert row["priority"] == 5


def test_max_two_invented_open(store):
    _clean_state(store)
    for i in range(4):
        _closed_mission(store, f"stale job {i}")
    out = CO.invent_work(store, OWNER, limit=5)
    assert len(out["invented"]) == 2
    waits = [sk for sk in out["skipped"]
             if "already open" in sk["reason"]]
    assert waits  # further invention waits
    # And again: the cap holds across runs.
    out2 = CO.invent_work(store, OWNER, limit=5)
    assert out2["invented"] == []


def test_dedupe_blocks_reinvent_while_open(store):
    _clean_state(store)
    _closed_mission(store, "stale job")
    first = CO.invent_work(store, OWNER, limit=1)
    assert len(first["invented"]) == 1
    second = CO.invent_work(store, OWNER, limit=1)
    assert second["invented"] == []
    assert any("7 days" in sk["reason"] for sk in second["skipped"])


def test_dedupe_blocks_recently_done_within_7_days(store):
    _clean_state(store)
    m = _closed_mission(store, "stale job")
    out = CO.invent_work(store, OWNER, limit=1)
    bid = out["invented"][0]["backlog_id"]
    # Simulate: the item was assigned and finished yesterday.
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(
        timespec="seconds")
    store._db.execute(
        "UPDATE work_backlog SET status = 'done', updated_at = ? "
        "WHERE id = ?", (yesterday, bid))
    store._db.commit()
    out2 = CO.invent_work(store, OWNER, limit=1)
    assert out2["invented"] == []
    assert any("7 days" in sk["reason"] for sk in out2["skipped"])


def test_reinvention_after_7_days_reopens_row(store):
    _clean_state(store)
    m = _closed_mission(store, "stale job")
    out = CO.invent_work(store, OWNER, limit=1)
    bid = out["invented"][0]["backlog_id"]
    # The finished row is 8 days old: re-invention is legitimate again —
    # the ORIGINAL row re-opens with fresh fields (history append-only,
    # nothing deleted, no duplicate row).
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(
        timespec="seconds")
    store._db.execute(
        "UPDATE work_backlog SET status = 'done', updated_at = ? "
        "WHERE id = ?", (old, bid))
    store._db.commit()
    out2 = CO.invent_work(store, OWNER, limit=1)
    assert len(out2["invented"]) == 1
    assert out2["invented"][0]["backlog_id"] == bid  # same row, reopened
    row = CO.list_backlog(store, OWNER)[0]
    assert row["id"] == bid and row["status"] == "open"
    # And now it is open again: a third invent is deduped, not duplicated.
    out3 = CO.invent_work(store, OWNER, limit=1)
    assert out3["invented"] == []
    assert len(CO.list_backlog(store, OWNER)) == 1


# ---------------------------------------------------------------------------
# Tick discipline: standing first, one invented per tick
# ---------------------------------------------------------------------------
def test_tick_prefers_standing_and_caps_invented(store):
    _clean_state(store)
    CO.add_backlog(store, OWNER, "Team health deep check", "health_check",
                   priority=2)  # one standing item, queue-leading
    for i in range(3):
        _closed_mission(store, f"stale job {i}")
    out = CO.invent_work(store, OWNER, limit=5)
    assert len(out["invented"]) == 2  # open cap
    rep = CO.tick(store, OWNER, max_assignments=5)
    assigned = rep["assigned"]
    # Standing health_check (pri 2) is assigned before any invented item;
    # exactly one invented assignment lands (1/tick cap).
    standing_first = [a for a in assigned
                      if "Invented" not in a["title"]]
    invented = [a for a in assigned if "Invented" in a["title"]]
    assert len(standing_first) >= 1
    assert assigned[0]["title"] == "Team health deep check"
    assert len(invented) == 1
    capped = [sk for sk in rep["skipped"] if "invented cap" in sk["reason"]]
    assert len(capped) == 1


def test_assignment_records_origin_via_backlog_join(store):
    _clean_state(store)
    CO.add_backlog(store, OWNER, "Team health deep check", "health_check",
                   priority=2)
    _closed_mission(store, "stale job")
    CO.invent_work(store, OWNER, limit=1)
    CO.tick(store, OWNER, max_assignments=5)
    rows = CO.recent_assignments(store, OWNER, limit=10)
    origins = {r["origin"] for r in rows}
    assert "standing" in origins
    assert "invented" in origins


# ---------------------------------------------------------------------------
# Weekly-report helper
# ---------------------------------------------------------------------------
def test_invented_report_counts(store):
    _clean_state(store)
    _closed_mission(store, "stale job")
    rep0 = CO.invented_report(store, OWNER, days=7)
    assert rep0 == {"days": 7, "invented": 0, "assigned": 0, "completed": 0}
    CO.invent_work(store, OWNER, limit=1)
    CO.tick(store, OWNER, max_assignments=3)
    rep = CO.invented_report(store, OWNER, days=7)
    assert rep["invented"] == 1
    assert rep["assigned"] == 1
    assert rep["completed"] == 1  # verify_recent built-in marks done


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------
def test_cli_invent_smoke(tmp_path, capsys):
    from luna_v2 import cli as CLI
    db = str(tmp_path / "cli.sqlite")
    assert CLI.main(["--db", db, "--owner", OWNER, "conductor",
                     "invent"]) == 0
    out = capsys.readouterr().out
    # Fresh DB: rotation-gap should fire for never-ran specialists.
    assert ("invented #" in out) or ("nothing worth inventing" in out)
    assert CLI.main(["--db", db, "--owner", OWNER, "conductor",
                     "backlog"]) == 0
    out2 = capsys.readouterr().out
    assert "backlog is empty" in out2 or "[invented]" in out2
