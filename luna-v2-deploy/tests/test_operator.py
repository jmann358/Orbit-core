"""Tests for the Operator specialist (luna_v2/operator.py).

v1 = read-only acts inside Luna's own workspace, everything audited.
Stdlib only.
"""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from luna_v2 import missions as M
from luna_v2 import operator as OP
from luna_v2.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "workspace"
    r.mkdir()
    (r / "notes.txt").write_text("hello operator\n", encoding="utf-8")
    sub = r / "subdir"
    sub.mkdir()
    (sub / "inner.txt").write_text("inner\n", encoding="utf-8")
    return r


# ---------------------------------------------------------------- read_file
def test_read_file_inside_root(store, root):
    res = OP.act(store, "jason", "read_file",
                 {"path": "notes.txt"}, root=root)
    assert res["outcome"] == "done"
    assert res["classification"] == "routine"
    assert res["content"] == "hello operator\n"
    assert res["truncated"] is False


def test_read_file_truncation_flag(store, root):
    big = root / "big.txt"
    big.write_bytes(b"x" * (OP.MAX_READ_BYTES + 10))
    res = OP.act(store, "jason", "read_file",
                 {"path": "big.txt"}, root=root)
    assert res["outcome"] == "done"
    assert res["truncated"] is True
    assert len(res["content"]) <= OP.MAX_READ_BYTES


def test_read_file_missing_is_clean_refusal(store, root):
    res = OP.act(store, "jason", "read_file",
                 {"path": "nope.txt"}, root=root)
    assert res["outcome"] == "refused"          # spec: clean refusal, not raise
    assert "no such file" in res["detail"]
    rows = OP.list_actions(store, "jason")
    assert any(r["outcome"] == "refused" and r["action"] == "read_file"
               for r in rows)


def test_read_file_on_directory_is_clean_refusal(store, root):
    res = OP.act(store, "jason", "read_file",
                 {"path": "subdir"}, root=root)
    assert res["outcome"] == "refused"          # spec: clean refusal, not raise
    assert "list_dir" in res["detail"]


def test_read_file_binary_is_clean_refusal(store, root):
    (root / "blob.bin").write_bytes(b"\xff\xfe\x00\x01garbage-bytes")
    res = OP.act(store, "jason", "read_file",
                 {"path": "blob.bin"}, root=root)
    assert res["outcome"] == "refused"
    assert "non-UTF8" in res["detail"] or "binary" in res["detail"]


def test_read_file_without_path_raises(store, root):
    with pytest.raises(OP.OperatorError):
        OP.act(store, "jason", "read_file", {}, root=root)


# ------------------------------------------------------------------ list_dir
def test_list_dir(store, root):
    res = OP.act(store, "jason", "list_dir", {"path": ""}, root=root)
    assert res["outcome"] == "done"
    assert "notes.txt" in res["entries"]
    assert "subdir/" in res["entries"]          # dir/file marker
    assert res["entries"] == sorted(res["entries"])


def test_list_dir_subdir(store, root):
    res = OP.act(store, "jason", "list_dir", {"path": "subdir"}, root=root)
    assert res["outcome"] == "done"
    assert res["entries"] == ["inner.txt"]


def test_list_dir_missing_is_clean_refusal(store, root):
    res = OP.act(store, "jason", "list_dir",
                 {"path": "nowhere"}, root=root)
    assert res["outcome"] == "refused"
    assert "no such directory" in res["detail"]


# ---------------------------------------------------------------- db_summary
def _seed_db(store):
    mid = store.create_mission("jason", "t", "o")
    sid = store.add_step(mid, "jason", "step one", M.ROUTINE,
                         store.next_seq(mid))
    sid2 = store.add_step(mid, "jason", "step two", M.ROUTINE,
                          store.next_seq(mid))
    M.complete_step(store, sid, result="r", evidence="e")
    return mid, sid, sid2


def test_db_summary_counts_match_seeded_db(store):
    _seed_db(store)
    store._db.execute(
        "CREATE TABLE IF NOT EXISTS specialist_runs "
        "(id INTEGER PRIMARY KEY, owner TEXT, status TEXT)")
    store._db.execute(
        "INSERT INTO specialist_runs (owner, status) VALUES ('jason','done')")
    store._db.commit()
    res = OP.act(store, "jason", "db_summary", {})
    assert res["outcome"] == "done"
    assert res["classification"] == "routine"
    s = res["summary"]
    assert s["missions_by_status"] == {"open": 1}
    assert s["steps_by_status"] == {"open": 1, "done": 1}
    assert s["receipts"] == 0
    assert s["specialist_runs_by_status"] == {"done": 1}


# ------------------------------------------------------------------- escapes
def test_dotdot_escape_refused(store, root):
    res = OP.act(store, "jason", "read_file",
                 {"path": "../secret.txt"}, root=root)
    assert res["outcome"] == "refused"
    assert "escape" in res["detail"]
    assert "outside the Luna workspace" in res["detail"]
    rows = OP.list_actions(store, "jason")
    esc = [r for r in rows if "escape" in r["detail"]]
    assert esc and esc[0]["outcome"] == "refused"


def test_absolute_path_outside_root_refused(store, root, tmp_path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("not yours\n", encoding="utf-8")
    res = OP.act(store, "jason", "read_file",
                 {"path": str(outside)}, root=root)
    assert res["outcome"] == "refused"
    assert "escape" in res["detail"]


def test_symlink_escape_refused(store, root, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("exfiltrate me\n", encoding="utf-8")
    link = root / "sneaky.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here")
    res = OP.act(store, "jason", "read_file",
                 {"path": "sneaky.txt"}, root=root)
    assert res["outcome"] == "refused"
    assert "escape" in res["detail"]


def test_list_dir_escape_refused(store, root):
    res = OP.act(store, "jason", "list_dir", {"path": ".."}, root=root)
    assert res["outcome"] == "refused"
    assert "escape" in res["detail"]


# ------------------------------------------------------ unknown/consequential
@pytest.mark.parametrize("action", ["write_file", "delete", "exec", "open_app"])
def test_unknown_actions_refused_as_consequential(store, root, action):
    target = root / "victim.txt"
    target.write_text("do not touch\n", encoding="utf-8")
    res = OP.act(store, "jason", action, {"path": "victim.txt"}, root=root)
    assert res["outcome"] == "refused"          # returned, not raised
    assert res["classification"] == "consequential"
    assert "Rowan" in res["detail"]
    # the named file is untouched
    assert target.read_text(encoding="utf-8") == "do not touch\n"
    rows = OP.list_actions(store, "jason")
    assert any(r["action"] == action and r["outcome"] == "refused"
               and r["classification"] == "consequential" for r in rows)


# ------------------------------------------------------------ audit trail
def test_audit_completeness_and_order(store, root):
    OP.act(store, "jason", "read_file", {"path": "notes.txt"}, root=root)
    OP.act(store, "jason", "read_file", {"path": "../x.txt"}, root=root)
    OP.act(store, "jason", "write_file", {"path": "y.txt"}, root=root)
    OP.act(store, "jason", "list_dir", {"path": ""}, root=root)
    rows = OP.list_actions(store, "jason")
    assert len(rows) == 4
    acts = [(r["action"], r["classification"], r["outcome"]) for r in rows]
    assert acts[0] == ("list_dir", "routine", "done")       # newest first
    assert acts[1] == ("write_file", "consequential", "refused")
    assert acts[2] == ("read_file", "routine", "refused")
    assert acts[3] == ("read_file", "routine", "done")     # oldest last
    assert all(json.loads(r["params_json"]) for r in rows)


def test_audit_is_owner_scoped(store, root):
    OP.act(store, "jason", "db_summary", {})
    OP.act(store, "someone_else", "db_summary", {})
    assert len(OP.list_actions(store, "jason")) == 1
    assert len(OP.list_actions(store, "someone_else")) == 1


def test_zero_provider_calls_and_no_writes():
    # Structural: operator.py never imports dispatch/broker and contains
    # no write/exec primitives.
    src = open(os.path.join(os.path.dirname(__file__), "..",
                            "luna_v2", "operator.py"),
               encoding="utf-8").read()
    for banned in ("dispatch", "broker", "subprocess", "os.system",
                   "open(", "write_bytes", "write_text", "unlink",
                   "mkdir", "rename", "shutil"):
        assert banned not in src, f"operator must not use {banned}"
    # profile caps: operator fetches nothing in v1; it may hold up to 2
    # provider calls of budget headroom but v1 uses zero (the source
    # check above proves no dispatch path exists in the module).
    from luna_v2.specialists import get_profile
    p = get_profile("operator")
    assert p.max_provider_calls_per_run <= 2
    assert p.max_fetches_per_run == 0
