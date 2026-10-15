"""Tests for the Workload engine: Jason's 10-deep queue law.

Jason's directive (2026-10-14): every worker carries 10 tasks,
nobody idles. The law as built: max 10 OPEN per specialist (11th
refused), max 2 ACTIVE (3rd start refused), block requires a
blocker note, fail requires a failure note, every transition
timestamped, and the board names idle specialists out of the full
39-name registry.
"""
import pytest

from luna_v2 import cli
from luna_v2 import specialists as SP
from luna_v2 import workload as WL
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "workload.db"))
    yield s
    s.close()


def _fill(store, name, n, **kw):
    return [WL.add_item(store, OWNER, name, f"{name} task {i}", **kw)
            for i in range(n)]


# ---------------------------------------------------------------------------
# Queue law: caps
# ---------------------------------------------------------------------------
def test_cap_ten_open_refuses_eleventh(store):
    _fill(store, "scout", 10)
    with pytest.raises(WL.WorkloadError, match="caps a queue at 10"):
        WL.add_item(store, OWNER, "scout", "one too many")
    # the refusal wrote nothing
    assert len(WL.list_items(store, OWNER, specialist="scout")) == 10


def test_done_and_failed_free_the_slot(store):
    rows = _fill(store, "scout", 10)
    WL.complete_item(store, OWNER, rows[0]["id"])
    WL.add_item(store, OWNER, "scout", "backfill after done")
    WL.fail_item(store, OWNER, rows[1]["id"], "the source vanished")
    WL.add_item(store, OWNER, "scout", "backfill after fail")
    assert WL.board(store, OWNER)["totals"]["open"] == 10


def test_blocked_items_still_count_as_open(store):
    rows = _fill(store, "builder", 10)
    WL.start_item(store, OWNER, rows[0]["id"])
    WL.block_item(store, OWNER, rows[0]["id"], "waiting on a key")
    with pytest.raises(WL.WorkloadError, match="caps a queue at 10"):
        WL.add_item(store, OWNER, "builder", "one too many")


def test_wip_two_active_refuses_third_start(store):
    rows = _fill(store, "scout", 4)
    WL.start_item(store, OWNER, rows[0]["id"])
    WL.start_item(store, OWNER, rows[1]["id"])
    with pytest.raises(WL.WorkloadError, match="WIP limit is 2"):
        WL.start_item(store, OWNER, rows[2]["id"])
    # the refused start left the item queued
    assert WL.list_items(store, OWNER, status="queued")


def test_blocked_frees_the_active_slot(store):
    rows = _fill(store, "scout", 3)
    WL.start_item(store, OWNER, rows[0]["id"])
    WL.start_item(store, OWNER, rows[1]["id"])
    WL.block_item(store, OWNER, rows[0]["id"], "needs a decision")
    WL.start_item(store, OWNER, rows[2]["id"])  # no refusal now
    b = WL.board(store, OWNER)
    scout = [e for e in b["specialists"]
             if e["specialist"] == "scout"][0]
    assert scout["active"] == 2 and scout["blocked"] == 1


# ---------------------------------------------------------------------------
# Transitions: notes required, legal paths only
# ---------------------------------------------------------------------------
def test_block_requires_a_blocker_note(store):
    rows = _fill(store, "scout", 1)
    WL.start_item(store, OWNER, rows[0]["id"])
    for bad in ("", "   ", None):
        with pytest.raises(WL.WorkloadError, match="blocker note"):
            WL.block_item(store, OWNER, rows[0]["id"], bad)
    assert WL.list_items(store, OWNER, status="blocked") == []


def test_fail_requires_a_failure_note(store):
    rows = _fill(store, "scout", 1)
    for bad in ("", "   ", None):
        with pytest.raises(WL.WorkloadError, match="failure note"):
            WL.fail_item(store, OWNER, rows[0]["id"], bad)
    r = WL.fail_item(store, OWNER, rows[0]["id"], "engine refused it")
    assert r["status"] == "failed"
    assert r["note"] == "engine refused it"
    assert r["finished_at"]


def test_transition_paths_are_legal_only(store):
    rows = _fill(store, "scout", 2)
    with pytest.raises(WL.WorkloadError, match="not active"):
        WL.block_item(store, OWNER, rows[0]["id"], "too early")
    with pytest.raises(WL.WorkloadError, match="not blocked"):
        WL.unblock_item(store, OWNER, rows[0]["id"])
    WL.start_item(store, OWNER, rows[0]["id"])
    with pytest.raises(WL.WorkloadError, match="not queued"):
        WL.start_item(store, OWNER, rows[0]["id"])
    WL.block_item(store, OWNER, rows[0]["id"], "waiting")
    with pytest.raises(WL.WorkloadError, match="unblock it first"):
        WL.complete_item(store, OWNER, rows[0]["id"])
    WL.unblock_item(store, OWNER, rows[0]["id"])
    r = WL.complete_item(store, OWNER, rows[0]["id"])
    assert r["status"] == "done"
    with pytest.raises(WL.WorkloadError, match="already done"):
        WL.fail_item(store, OWNER, rows[0]["id"], "too late")


def test_unblock_clears_the_blocker(store):
    rows = _fill(store, "scout", 1)
    WL.start_item(store, OWNER, rows[0]["id"])
    WL.block_item(store, OWNER, rows[0]["id"], "storm took the host")
    r = WL.unblock_item(store, OWNER, rows[0]["id"])
    assert r["status"] == "queued" and r["blocker"] == ""


def test_transitions_are_timestamped(store):
    r = _fill(store, "scout", 1)[0]
    assert r["created_at"] and r["updated_at"]
    assert r["started_at"] is None and r["finished_at"] is None
    r = WL.start_item(store, OWNER, r["id"])
    assert r["started_at"] and r["started_at"] >= r["created_at"]
    assert r["updated_at"] >= r["created_at"]
    r = WL.complete_item(store, OWNER, r["id"])
    assert r["finished_at"] and r["finished_at"] >= r["started_at"]


def test_add_validates_specialist_and_title(store):
    with pytest.raises(WL.WorkloadError, match="unknown specialist"):
        WL.add_item(store, OWNER, "nobody", "phantom work")
    with pytest.raises(WL.WorkloadError, match="needs a title"):
        WL.add_item(store, OWNER, "scout", "   ")


def test_missing_item_is_a_clean_refusal(store):
    with pytest.raises(WL.WorkloadError, match="no work item 99"):
        WL.start_item(store, OWNER, 99)


# ---------------------------------------------------------------------------
# Board math + idle list
# ---------------------------------------------------------------------------
def test_board_math_and_idle_list(store):
    rows = _fill(store, "scout", 4)
    _fill(store, "builder", 2)
    WL.start_item(store, OWNER, rows[0]["id"])
    WL.start_item(store, OWNER, rows[1]["id"])
    WL.block_item(store, OWNER, rows[0]["id"], "waiting on weather")
    WL.complete_item(store, OWNER, rows[2]["id"])
    WL.fail_item(store, OWNER, rows[3]["id"], "target moved")
    b = WL.board(store, OWNER)
    by_name = {e["specialist"]: e for e in b["specialists"]}
    assert by_name["scout"] == {
        "specialist": "scout", "queued": 0, "active": 1,
        "blocked": 1, "done": 1, "failed": 1, "open": 2}
    assert by_name["builder"]["open"] == 2
    t = b["totals"]
    assert (t["queued"], t["active"], t["blocked"], t["done"],
            t["failed"], t["open"]) == (2, 1, 1, 1, 1, 4)
    # idle = everyone registered except scout and builder
    assert set(b["idle"]) == set(SP.SPECIALISTS) - {"scout", "builder"}
    # done/failed-only specialists are idle too (zero OPEN)
    assert "weaver" in b["idle"]


def test_board_covers_exactly_the_registry(store):
    b = WL.board(store, OWNER)
    names = [e["specialist"] for e in b["specialists"]]
    assert sorted(names) == sorted(SP.SPECIALISTS)
    assert len(names) == 39
    # an untouched database: the whole court is idle, by name
    assert b["idle"] == sorted(SP.SPECIALISTS)
    assert "39 idle specialist" in WL.summary_line(store, OWNER)


# ---------------------------------------------------------------------------
# CLI smoke + wiring pins
# ---------------------------------------------------------------------------
def test_cli_alias_points_at_workload():
    assert cli.WL is WL


def test_cli_end_to_end(tmp_path, capsys):
    db = str(tmp_path / "wl-cli.db")
    base = ["--db", db, "--owner", OWNER, "workload"]
    assert cli.main(base + ["add", "--specialist", "scout",
                            "--title", "sweep the field",
                            "--source", "outrider watch"]) == 0
    out = capsys.readouterr().out
    assert "work item 1 queued for scout" in out
    assert cli.main(base + ["list", "--specialist", "scout"]) == 0
    out = capsys.readouterr().out
    assert "[queued] scout" in out and "sweep the field" in out
    assert cli.main(base + ["start", "1"]) == 0
    assert cli.main(base + ["block", "1", "--blocker",
                            "fog over the field"]) == 0
    out = capsys.readouterr().out
    assert "blocked: fog over the field" in out
    assert cli.main(base + ["unblock", "1"]) == 0
    assert cli.main(base + ["start", "1"]) == 0
    assert cli.main(base + ["done", "1"]) == 0
    assert cli.main(base + ["add", "--specialist", "scout",
                            "--title", "doomed errand"]) == 0
    assert cli.main(base + ["fail", "2", "--note",
                            "the bridge was out"]) == 0
    out = capsys.readouterr().out
    assert "failed: the bridge was out" in out
    assert cli.main(base + ["board"]) == 0
    out = capsys.readouterr().out
    assert "WORKLOAD BOARD" in out
    assert "1 done · 1 failed" in out
    assert "IDLE (no open work):" in out


def test_cli_cap_refusal_surfaces_as_error(tmp_path, capsys):
    db = str(tmp_path / "wl-cap.db")
    base = ["--db", db, "--owner", OWNER, "workload"]
    for i in range(10):
        assert cli.main(base + ["add", "--specialist", "jester",
                                "--title", f"bit {i}"]) == 0
    capsys.readouterr()
    rc = cli.main(base + ["add", "--specialist", "jester",
                          "--title", "one too many"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "caps a queue at 10" in err


def test_conductor_status_carries_the_workload_line(tmp_path, capsys):
    db = str(tmp_path / "wl-cond.db")
    assert cli.main(["--db", db, "--owner", OWNER, "workload",
                     "add", "--specialist", "warden",
                     "--title", "walk the wall"]) == 0
    capsys.readouterr()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "conductor", "status"]) == 0
    out = capsys.readouterr().out
    assert "workload: 1 open (1 queued · 0 active · 0 blocked)" in out
    assert "38 idle specialist(s)" in out
