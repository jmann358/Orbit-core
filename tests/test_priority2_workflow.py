"""Priority 2: review-only workshop -> manifest -> guarded sandbox."""
import hashlib
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from luna.patch_manifest import proposal_fingerprint
from luna.restricted_runner import _command, run_verified_candidate
from luna.workshop import stage_proposal


def fixture(root):
    (root / "luna").mkdir()
    (root / "tests").mkdir()
    (root / "app.py").write_text("VALUE = 1\n")
    (root / "requirements.txt").write_text("pytest\n")
    (root / "luna" / "__init__.py").write_text("")
    source = root / "luna" / "development.py"
    source.write_text("VALUE = 1\n")
    (root / "tests" / "test_sample.py").write_text(
        "from luna.development import VALUE\n\ndef test_value(): assert VALUE == 2\n"
    )
    base = hashlib.sha256(source.read_bytes()).hexdigest()
    changes = [{"path": "luna/development.py", "base_sha256": base,
                "replacement": "VALUE = 2\n"}]
    return source, changes


def test_proposal_is_review_only_and_fingerprint_stable(tmp_path):
    source, changes = fixture(tmp_path)
    original = source.read_bytes()
    report = stage_proposal(tmp_path, changes, ["tests/test_sample.py"])
    assert report["fingerprint"] == proposal_fingerprint(report["manifest"])
    assert report["manifest"]["files"][0]["replacement_sha256"] == hashlib.sha256(b"VALUE = 2\n").hexdigest()
    assert report["diffs"][0]["path"] == "luna/development.py"
    assert report["syntax_valid"] and report["workspace_deleted"]
    assert report["base_revisions_verified"] and report["replacement_contents_verified"]
    assert report["applied"] is False and report["tests_run"] is False
    assert source.read_bytes() == original


def test_reject_bad_proposals(tmp_path):
    source, changes = fixture(tmp_path)
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, changes * 2)
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, [{**changes[0], "shell": "whoami"}])
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, [{**changes[0], "path": "app.py"}])
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, [{**changes[0], "replacement": "VALUE = 1\n"}])
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, changes, ["tests/test_sample.py;whoami"])
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, [{**changes[0], "replacement": "def broken(:\n"}])
    source.write_text("VALUE = 99\n")
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, changes, ["tests/test_sample.py"])


def test_reject_symlinked_patch_root(tmp_path):
    source, changes = fixture(tmp_path)
    external = tmp_path / "elsewhere.py"
    external.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(external)
    with pytest.raises(ValueError):
        stage_proposal(tmp_path, changes)


def test_runner_requires_separate_explicit_approval(tmp_path):
    _, changes = fixture(tmp_path)
    report = stage_proposal(tmp_path, changes, ["tests/test_sample.py"])
    with pytest.raises(PermissionError):
        run_verified_candidate(tmp_path, report["manifest"], {"luna/development.py": "VALUE = 2\n"},
                               expected_fingerprint=report["fingerprint"])
    with pytest.raises(ValueError):
        run_verified_candidate(tmp_path, report["manifest"], {"luna/development.py": "VALUE = 2\n"},
                               expected_fingerprint="a"*64, approved=True)


def test_runner_rejects_tampered_replacement_before_any_execution(tmp_path):
    _, changes = fixture(tmp_path)
    report = stage_proposal(tmp_path, changes, ["tests/test_sample.py"])
    with patch("luna.restricted_runner.subprocess.run") as run:
        with pytest.raises(ValueError):
            run_verified_candidate(tmp_path, report["manifest"],
                                   {"luna/development.py": "VALUE = 888\n"},
                                   expected_fingerprint=report["fingerprint"], approved=True)
        run.assert_not_called()


def test_runner_fails_closed_without_bwrap(tmp_path):
    _, changes = fixture(tmp_path)
    report = stage_proposal(tmp_path, changes, ["tests/test_sample.py"])
    with patch("luna.restricted_runner.shutil.which", return_value=None), patch(
            "luna.restricted_runner.subprocess.run") as run:
        with pytest.raises(RuntimeError, match="not installed"):
            run_verified_candidate(tmp_path, report["manifest"],
                                   {"luna/development.py": "VALUE = 2\n"},
                                   expected_fingerprint=report["fingerprint"], approved=True)
        run.assert_not_called()


def test_runner_requires_existing_unmodified_trusted_test(tmp_path):
    _, changes = fixture(tmp_path)
    report = stage_proposal(tmp_path, changes, ["tests/test_not_present.py"])
    with patch("luna.restricted_runner.subprocess.run") as run:
        with pytest.raises(ValueError):
            run_verified_candidate(tmp_path, report["manifest"],
                                   {"luna/development.py": "VALUE = 2\n"},
                                   expected_fingerprint=report["fingerprint"], approved=True)
        run.assert_not_called()


def test_runner_sandbox_invocation_and_unmodified_host(tmp_path):
    source, changes = fixture(tmp_path)
    original = source.read_bytes()
    report = stage_proposal(tmp_path, changes, ["tests/test_sample.py"])
    with patch("luna.restricted_runner._runner_binary", return_value="/usr/bin/bwrap"), patch(
            "luna.restricted_runner._command",
            return_value=["/usr/bin/bwrap", "--unshare-all", "--", "python"]) as command, patch(
            "luna.restricted_runner.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0)) as run:
        result = run_verified_candidate(tmp_path, report["manifest"],
                                        {"luna/development.py": "VALUE = 2\n"},
                                        expected_fingerprint=report["fingerprint"], approved=True)
    assert result["passed"] and result["runner"] == "bubblewrap"
    assert result["automatic_execution"] is False and result["live_patch_applied"] is False
    assert source.read_bytes() == original
    assert run.call_args.kwargs["timeout"] == 30
    assert run.call_args.kwargs["stdin"] == subprocess.DEVNULL
    assert "shell" not in run.call_args.kwargs
    assert command.call_args.args[2] == ["tests/test_sample.py"]


def test_runner_timeout_is_reported_without_host_mutation(tmp_path):
    source, changes = fixture(tmp_path)
    report = stage_proposal(tmp_path, changes, ["tests/test_sample.py"])
    with patch("luna.restricted_runner._runner_binary", return_value="/usr/bin/bwrap"), patch(
            "luna.restricted_runner._command", return_value=["bwrap"]), patch(
            "luna.restricted_runner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["bwrap"], 30)):
        result = run_verified_candidate(tmp_path, report["manifest"],
                                        {"luna/development.py": "VALUE = 2\n"},
                                        expected_fingerprint=report["fingerprint"], approved=True)
    assert result["timed_out"] and not result["passed"]
    assert source.read_text() == "VALUE = 1\n"


def test_bubblewrap_command_never_shares_host_root_or_network(tmp_path):
    with patch("luna.restricted_runner._python_mount", return_value=("/usr/bin/python3", [])):
        argv = _command("/usr/bin/bwrap", tmp_path, ["tests/test_sample.py"])
    assert "--unshare-all" in argv
    assert "--clearenv" in argv and "--die-with-parent" in argv
    assert "--share-net" not in argv
    assert argv[argv.index("--uid") + 1] == "0"  # root only inside mapped user namespace
    assert argv[argv.index("--gid") + 1] == "0"
    assert "--ro-bind" in argv and "--tmpfs" in argv
    assert "--bind" not in argv
    assert argv[-1] == "tests/test_sample.py"


def test_workshop_proposal_api(tmp_path):
    from fastapi.testclient import TestClient
    from app import app
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / "luna" / "development.py"
    original = source.read_bytes()
    proposal = {
        "changes": [{
            "path": "luna/development.py",
            "base_sha256": hashlib.sha256(original).hexdigest(),
            "replacement": original.decode("utf-8") + "\n# pending-review-only\n",
        }],
        "tests": ["tests/test_development_engine.py"],
    }
    client = TestClient(app)
    response = client.post("/development/workshop/proposal", json=proposal)
    assert response.status_code == 200, response.text
    assert response.json()["manifest"]["requires_explicit_review"]
    assert source.read_bytes() == original
    rejected = client.post("/development/workshop/proposal", json={
        "changes": [{**proposal["changes"][0], "path": "app.py"}]})
    assert rejected.status_code == 400
    assert client.get("/development/runner/preflight").status_code == 200
