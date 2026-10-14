"""Tests for the Warden: Sentinel's partner at the gate.

The Warden scans INCOMING material and can only PASS or HOLD — there
is deliberately no approve/release function. Findings name the
pattern family + line reference, never the matched value.
"""

import os
import tempfile

import pytest

from luna_v2.store import Store
from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2 import warden as W

FAKE_KEY = "sk-FAKEFAKEFAKEFAKEFAKEFAKE"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _guardian_hold_count(store):
    return len([r for r in G.inbox(store, "jason")
                if r["check_name"] == "warden_hold"
                and r["status"] in ("open", "acknowledged")])


# ---------------------------------------------------------------------------
# Clean material passes
# ---------------------------------------------------------------------------
def test_clean_stdlib_code_passes(store):
    text = ("import json\nimport math\n\n"
            "def f():\n"
            "    return json.dumps({'n': math.floor(2.7)})\n")
    out = W.scan_text(store, "jason", "clean.py", "code", text)
    assert out["verdict"] == "pass"
    assert out["findings"] == []
    assert _guardian_hold_count(store) == 0


def test_text_kind_with_url_passes(store):
    # A URL in plain text is a reference, not an egress event.
    text = "see https://docs.python.org/3/library/urllib.html for details"
    out = W.scan_text(store, "jason", "a-note.txt", "text", text)
    assert out["verdict"] == "pass"
    assert _guardian_hold_count(store) == 0


def test_invalid_kind_refused(store):
    with pytest.raises(M.LunaError):
        W.scan_text(store, "jason", "x", "binary", "text")


# ---------------------------------------------------------------------------
# Threats hold — and name only the family
# ---------------------------------------------------------------------------
def test_egress_snippet_holds(store):
    text = ("import urllib.request\n"
            "urllib.request.urlopen('https://example.com/data')\n")
    out = W.scan_text(store, "jason", "fetch-patch.py", "code", text)
    assert out["verdict"] == "hold"
    assert any(f.startswith("egress:") for f in out["findings"])


def test_secret_path_access_holds_without_echoing_value(store):
    path_value = "/home/jaysmac/.ssh/id_rsa"
    text = f"key = open({path_value!r}).read()\n"
    out = W.scan_text(store, "jason", "sneaky.py", "code", text)
    assert out["verdict"] == "hold"
    assert any(f.startswith("secret-access:") for f in out["findings"])
    blob = "\n".join(out["findings"])
    assert ".ssh" in blob  # the family/pattern name, not the full path
    assert "jaysmac" not in blob


def test_credential_shaped_string_hold_names_family_only(store):
    text = f"token = {FAKE_KEY!r}\n"
    out = W.scan_text(store, "jason", "leaky.py", "code", text)
    assert out["verdict"] == "hold"
    assert any("secret: openai_key" in f for f in out["findings"])
    blob = "\n".join(out["findings"])
    assert FAKE_KEY not in blob  # never echo the value


def test_subprocess_holds(store):
    text = "import subprocess\nsubprocess.run(['ls', '-la'])\n"
    out = W.scan_text(store, "jason", "run.py", "code", text)
    assert out["verdict"] == "hold"
    assert any(f.startswith("shell-exec:") for f in out["findings"])


def test_non_stdlib_import_is_a_finding(store):
    text = "import requests\nprint('hi')\n"
    out = W.scan_text(store, "jason", "needs.py", "code", text)
    assert out["verdict"] == "hold"
    assert any(f.startswith("dependency:") and "requests" in f
               for f in out["findings"])


def test_own_package_import_is_not_a_dependency(store):
    # Every luna_v2 module imports the house package; the Warden does
    # not cry wolf at its own house.
    text = ("from luna_v2 import guardian as G\n"
            "from luna_v2 import missions as M\n"
            "import os\n"
            "print('ok')\n")
    out = W.scan_text(store, "jason", "own-module.py", "code", text)
    assert out["verdict"] == "pass"


def test_path_escape_holds(store):
    text = "open('../../secrets.txt', 'w').write('x')\n"
    out = W.scan_text(store, "jason", "esc.py", "code", text)
    assert out["verdict"] == "hold"
    assert any(f.startswith("path-escape:") for f in out["findings"])


# ---------------------------------------------------------------------------
# Holds file exactly one Guardian warning (dedupe does its job)
# ---------------------------------------------------------------------------
def test_hold_files_one_guardian_warning(store):
    out = W.scan_text(store, "jason", "held-once.py", "code",
                      "import subprocess\nsubprocess.run(['x'])\n")
    assert out["verdict"] == "hold"
    assert _guardian_hold_count(store) == 1
    # Same item held again: no second suggestion filed.
    W.scan_text(store, "jason", "held-once.py", "code",
                "import subprocess\nsubprocess.run(['y'])\n")
    assert _guardian_hold_count(store) == 1


def test_guardian_failure_does_not_break_the_scan(store, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("guardian is down")
    monkeypatch.setattr(G, "file_suggestion", _boom)
    out = W.scan_text(store, "jason", "still-held.py", "code",
                      "import subprocess\nsubprocess.run(['x'])\n")
    assert out["verdict"] == "hold"  # the hold stands on the scan record


# ---------------------------------------------------------------------------
# scan_file
# ---------------------------------------------------------------------------
def test_scan_file_py_is_scanned_as_code(store):
    with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False) as f:
        f.write("import json\nprint(json.dumps({}))\n")
        path = f.name
    try:
        out = W.scan_file(store, "jason", path)
        assert out["kind"] == "code"
        assert out["verdict"] == "pass"
    finally:
        os.unlink(path)


def test_scan_file_refuses_oversized_files(store):
    with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False) as f:
        f.write("x = 1\n" * ((W.MAX_FILE_BYTES // 6) + 10))
        path = f.name
    try:
        with pytest.raises(M.LunaError):
            W.scan_file(store, "jason", path)
    finally:
        os.unlink(path)


def test_scan_file_missing_path_refused(store):
    with pytest.raises(M.LunaError):
        W.scan_file(store, "jason", "/no/such/file.py")
