"""Tests for Luna's Builder specialist (luna_v2/builder.py).

Hermetic: each test builds a tmp_path mini-project with one module and
one stdlib-unittest test file; the test command is [sys.executable,
"-m", "unittest"] run inside a disposable sandbox copy. pytest itself
(the one in ~/workspace/.pylibs) is not needed for the fixtures.
"""

import sys
import tempfile
from pathlib import Path

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import builder as BL

OWNER = "jason"
CALC_TARGET = "calc.py"

ORIGINAL_CALC = 'def add(a, b):\n    return a + b\n'

TEST_FILE = (
    "import unittest\n"
    "import calc\n\n\n"
    "class CalcTest(unittest.TestCase):\n"
    "    def test_add(self):\n"
    "        self.assertEqual(calc.add(2, 3), 5)\n\n\n"
    'if __name__ == "__main__":\n'
    "    unittest.main()\n"
)

IMPROVED_CALC = (
    '"""Simple arithmetic helpers."""\n'
    "\n\n"
    "def add(a, b):\n"
    '    """Add two numbers."""\n'
    "    return a + b\n"
    "\n\n"
    "def sub(a, b):\n"
    '    """Subtract b from a."""\n'
    "    return a - b\n"
)

BROKEN_CALC = 'def add(a, b):\n    return a - b  # wrong: breaks test_add\n'


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "builder.db"))
    B.seed_providers(s, OWNER)
    yield s
    s.close()


def _write_project(root: Path, calc_source: str = ORIGINAL_CALC) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "calc.py").write_text(calc_source, encoding="utf-8")
    (root / "test_calc.py").write_text(TEST_FILE, encoding="utf-8")
    return root


def _test_command():
    return [sys.executable, "-m", "unittest"]


def _fake_transport(content: str):
    def transport(provider, prompt):
        return content, {"requests": 1.0, "tokens": 42.0}
    return transport


def _counting_transport():
    calls = []

    def transport(provider, prompt):
        calls.append((provider, prompt))
        return ORIGINAL_CALC, {"requests": 1.0, "tokens": 1.0}
    transport.calls = calls
    return transport


def _no_sandbox_leftover():
    return [d for d in Path(tempfile.gettempdir()).iterdir()
            if d.is_dir() and d.name.startswith(BL.SANDBOX_PREFIX)]


# ---------------------------------------------------------------------------
# Happy path: improved draft -> done, diff recorded, original untouched
# ---------------------------------------------------------------------------
def test_improved_run_is_done_and_original_untouched(store, tmp_path):
    project = _write_project(tmp_path / "proj")
    before = (project / CALC_TARGET).read_bytes()

    row = BL.build(store, OWNER, "add a sub() helper with docstrings",
                   project_dir=str(project), target_relpath=CALC_TARGET,
                   test_command=_test_command(),
                   transport=_fake_transport(IMPROVED_CALC))

    assert row["status"] == "done"
    assert row["test_exit_code"] == 0
    assert "def sub" in row["proposed_content"]
    assert "def sub" in row["diff_text"]
    assert f"{CALC_TARGET} (current)" in row["diff_text"]
    assert f"{CALC_TARGET} (proposed)" in row["diff_text"]
    # the original project is never written to
    assert (project / CALC_TARGET).read_bytes() == before
    # the sandbox is gone
    assert _no_sandbox_leftover() == []


# ---------------------------------------------------------------------------
# Broken draft -> failed, but still recorded with test evidence + diff
# ---------------------------------------------------------------------------
def test_breaking_run_is_failed_with_test_evidence(store, tmp_path):
    project = _write_project(tmp_path / "proj")

    row = BL.build(store, OWNER, "change add to subtract",
                   project_dir=str(project), target_relpath=CALC_TARGET,
                   test_command=_test_command(),
                   transport=_fake_transport(BROKEN_CALC))

    assert row["status"] == "failed"
    assert row["test_exit_code"] != 0
    assert row["test_tail"]  # the failing unittest output is evidence
    assert row["diff_text"]  # the draft is still reviewable
    assert "-    return a + b" in row["diff_text"]
    assert "+    return a - b  # wrong: breaks test_add" in row["diff_text"]
    assert _no_sandbox_leftover() == []


# ---------------------------------------------------------------------------
# Refusals: before any provider call, nothing recorded
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("relpath", ["../evil.py", "sub/../../evil.py",
                                     "/abs/evil.py", ""])
def test_path_escapes_and_blanks_refused_with_zero_spend(store, tmp_path,
                                                         relpath):
    project = _write_project(tmp_path / "proj")
    (tmp_path / "evil.py").write_text("x = 1")
    transport = _counting_transport()
    with pytest.raises(BL.BuilderRefused):
        BL.build(store, OWNER, "do harm", project_dir=str(project),
                 target_relpath=relpath, test_command=_test_command(),
                 transport=transport)
    assert transport.calls == []
    assert BL.list_runs(store, OWNER) == []


def test_oversized_target_refused_with_zero_spend(store, tmp_path):
    project = _write_project(tmp_path / "proj")
    big = "x = 1\n" * (BL.MAX_TARGET_BYTES // 6 + 100)
    (project / "big.py").write_text(big, encoding="utf-8")
    assert (project / "big.py").stat().st_size > BL.MAX_TARGET_BYTES
    transport = _counting_transport()
    with pytest.raises(BL.BuilderRefused):
        BL.build(store, OWNER, "rewrite big.py", project_dir=str(project),
                 target_relpath="big.py", test_command=_test_command(),
                 transport=transport)
    assert transport.calls == []


def test_missing_target_refused_with_zero_spend(store, tmp_path):
    project = _write_project(tmp_path / "proj")
    transport = _counting_transport()
    with pytest.raises(BL.BuilderRefused):
        BL.build(store, OWNER, "rewrite", project_dir=str(project),
                 target_relpath="nope.py", test_command=_test_command(),
                 transport=transport)
    assert transport.calls == []


def test_missing_project_dir_refused(store, tmp_path):
    transport = _counting_transport()
    with pytest.raises(BL.BuilderRefused):
        BL.build(store, OWNER, "rewrite",
                 project_dir=str(tmp_path / "no_such_dir"),
                 target_relpath=CALC_TARGET, test_command=_test_command(),
                 transport=transport)
    assert transport.calls == []


def test_no_transport_refused(store, tmp_path):
    project = _write_project(tmp_path / "proj")
    with pytest.raises(BL.BuilderRefused):
        BL.build(store, OWNER, "rewrite", project_dir=str(project),
                 target_relpath=CALC_TARGET, test_command=_test_command(),
                 transport=None)


def test_empty_test_command_refused_with_zero_spend(store, tmp_path):
    project = _write_project(tmp_path / "proj")
    transport = _counting_transport()
    with pytest.raises(BL.BuilderRefused):
        BL.build(store, OWNER, "rewrite", project_dir=str(project),
                 target_relpath=CALC_TARGET, test_command=[],
                 transport=transport)
    assert transport.calls == []


def test_empty_task_refused(store, tmp_path):
    project = _write_project(tmp_path / "proj")
    with pytest.raises(BL.BuilderRefused):
        BL.build(store, OWNER, "   ", project_dir=str(project),
                 target_relpath=CALC_TARGET, test_command=_test_command(),
                 transport=_fake_transport(IMPROVED_CALC))


# ---------------------------------------------------------------------------
# Record access
# ---------------------------------------------------------------------------
def test_get_and_list_runs(store, tmp_path):
    project = _write_project(tmp_path / "proj")
    row = BL.build(store, OWNER, "add sub()", project_dir=str(project),
                   target_relpath=CALC_TARGET,
                   test_command=_test_command(),
                   transport=_fake_transport(IMPROVED_CALC))
    fetched = BL.get_run(store, row["id"])
    assert fetched["task"] == "add sub()"
    assert fetched["target_relpath"] == CALC_TARGET
    assert BL.get_run(store, 999999) is None
    mine = BL.list_runs(store, OWNER)
    assert [r["id"] for r in mine] == [row["id"]]
    assert BL.list_runs(store, "someone_else") == []
