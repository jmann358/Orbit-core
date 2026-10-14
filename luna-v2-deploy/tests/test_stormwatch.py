"""Tests for storm mode (luna_v2/stormwatch.py).

Jason's design: Luna braces at official NWS *warnings* only (never
watches/advisories), keeps working, snapshots her database the safe
way, and after the storm proves nothing was lost. A failed weather
check must change nothing.
"""

import sqlite3
from pathlib import Path

import pytest

from luna_v2 import stormwatch as SW
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _alert(event, status="Actual", headline=None):
    return {"properties": {"event": event, "status": status,
                           "headline": headline or f"{event} in effect"}}


def _fetch(*alerts):
    def fetch(url):
        assert "api.weather.gov" in url
        return {"features": list(alerts)}
    return fetch


def _seed(store):
    mid = store.create_mission(OWNER, "Seed mission", "proof")
    return mid


def _snapshots(store):
    return store._db.execute(
        "SELECT * FROM storm_snapshots WHERE owner = ? ORDER BY id",
        (OWNER,)).fetchall()


def _events(store, kind=None):
    q = "SELECT * FROM storm_events WHERE owner = ?"
    args = [OWNER]
    if kind:
        q += " AND kind = ?"
        args.append(kind)
    return store._db.execute(q + " ORDER BY id", args).fetchall()


def _mode(store):
    return SW.status(store, OWNER)["mode"]


def test_no_home_set_raises(store):
    with pytest.raises(SW.StormError):
        SW.check(store, OWNER, fetcher=_fetch())


def test_watch_advisory_and_test_warning_do_not_brace(store):
    _seed(store)
    SW.set_home(store, OWNER, 42.0, -71.0)
    out = SW.check(store, OWNER, fetcher=_fetch(
        _alert("Severe Thunderstorm Watch"),
        _alert("Heat Advisory"),
        _alert("Tornado Warning", status="Test")))
    assert out["mode"] == "normal" and out["changed"] is False
    assert _mode(store) == "normal"
    assert _snapshots(store) == []
    assert _events(store, "braced") == []


def test_warning_braces_with_verified_snapshot(store):
    mid = _seed(store)
    SW.set_home(store, OWNER, 42.0, -71.0)
    out = SW.check(store, OWNER, fetcher=_fetch(
        _alert("Severe Thunderstorm Warning",
               headline="Severe Thunderstorm Warning issued for home")))
    assert out["mode"] == "braced" and out["changed"] is True
    assert _mode(store) == "braced"
    snaps = _snapshots(store)
    assert len(snaps) == 1
    snap_path = Path(snaps[0]["path"])
    assert snap_path.is_file()
    assert Path(str(snap_path) + ".note.txt").is_file()
    assert "1 mission(s) open" in snaps[0]["note"]
    # the snapshot is a real, readable copy of the database
    conn = sqlite3.connect(f"file:{snap_path}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0] == 1
        assert conn.execute("SELECT title FROM missions").fetchone()[0] == \
            "Seed mission"
    finally:
        conn.close()
    assert len(_events(store, "braced")) == 1
    # Rowan hears about it through Guardian's inbox
    rows = store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE check_name = "
        "'storm_mode'").fetchall()
    assert len(rows) == 1 and rows[0]["severity"] == "info"
    assert mid  # silence linter; mission id used implicitly above


def test_recheck_while_braced_is_quiet(store):
    _seed(store)
    SW.set_home(store, OWNER, 42.0, -71.0)
    fetch = _fetch(_alert("Tornado Warning"))
    SW.check(store, OWNER, fetcher=fetch)
    out = SW.check(store, OWNER, fetcher=fetch)
    assert out["changed"] is False and out["mode"] == "braced"
    assert len(_snapshots(store)) == 1
    assert len(_events(store, "braced")) == 1


def test_clear_runs_sweep_and_reports_ok(store):
    _seed(store)
    SW.set_home(store, OWNER, 42.0, -71.0)
    SW.check(store, OWNER, fetcher=_fetch(_alert("Tornado Warning")))
    out = SW.check(store, OWNER, fetcher=_fetch())
    assert out["mode"] == "normal" and out["changed"] is True
    assert out["sweep"]["ok"] is True
    assert out["sweep"]["integrity"] == "ok"
    assert out["sweep"]["compared_to_snapshot"] is True
    assert _mode(store) == "normal"
    assert len(_events(store, "cleared")) == 1
    assert len(_events(store, "sweep")) == 1


def test_fetch_failure_changes_nothing(store):
    _seed(store)
    SW.set_home(store, OWNER, 42.0, -71.0)

    def boom(url):
        raise OSError("network unreachable")

    out = SW.check(store, OWNER, fetcher=boom)
    assert out["changed"] is False and out["error"]
    assert _mode(store) == "normal"
    assert _snapshots(store) == []
    assert len(_events(store, "check_failed")) == 1
    # and a failure while braced must not clear the brace either
    SW.check(store, OWNER, fetcher=_fetch(_alert("Tornado Warning")))
    out = SW.check(store, OWNER, fetcher=boom)
    assert out["mode"] == "braced" and _mode(store) == "braced"


def test_snapshot_retention_keeps_three(store):
    _seed(store)
    for i in range(4):
        SW.snapshot(store, OWNER, reason=f"manual {i}")
    snaps = _snapshots(store)
    assert len(snaps) == SW.KEEP_SNAPSHOTS == 3
    assert all(Path(r["path"]).is_file() for r in snaps)


def test_sweep_detects_lost_receipt(store):
    mid = _seed(store)
    store.add_step(mid, OWNER, "only step", "routine", 1)
    store.update_mission(mid, status="closed")
    store.add_receipt(mid, OWNER, "done and proven", "{}")
    SW.snapshot(store, OWNER, reason="pre-storm")
    store._db.execute("DELETE FROM receipts WHERE mission_id = ?", (mid,))
    store._db.commit()
    out = SW.sweep(store, OWNER)
    assert out["ok"] is False
    assert any("receipts fell" in p for p in out["problems"])
    rows = store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE check_name = "
        "'storm_mode' AND severity = 'warning'").fetchall()
    assert len(rows) == 1


def test_restore_round_trip(tmp_path):
    db = tmp_path / "live.db"
    s = Store(str(db))
    s.create_mission(OWNER, "Before storm", "")
    SW.snapshot(s, OWNER, reason="pre-storm")
    snap_path = _snapshots(s)[0]["path"]
    s.create_mission(OWNER, "After snapshot", "")
    assert s.list_missions(OWNER)[0] is not None
    assert len(s.list_missions(OWNER)) == 2
    s.close()
    out = SW.restore(str(db), snap_path)
    assert out["safety_copy"] and Path(out["safety_copy"]).is_file()
    s2 = Store(str(db))
    try:
        titles = [m["title"] for m in s2.list_missions(OWNER)]
        assert titles == ["Before storm"]
    finally:
        s2.close()


def test_module_makes_no_provider_calls():
    src = Path(SW.__file__).read_text(encoding="utf-8")
    assert "import dispatch" not in src and "from . import" in src
    assert "broker" not in src.split('"""')[2]  # past the docstring
