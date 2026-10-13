"""Offline regression coverage for workflow-pinned launch guard consistency.

Only disposable synthetic text is used; tests do not run the launcher, fetch
GitHub, touch a personal database, change policy or grant an authorization.
"""
from pathlib import Path

from scripts import check_release_guard


def _write_case(tmp_path, *, pinned=None, workflow=b"name: ORBIT checks\n"):
    runner = tmp_path / "verify_and_launch.sh"
    source = check_release_guard.git_blob_sha(workflow)
    runner.write_text(
        f'TRUSTED_WORKFLOW_BLOB="{pinned or source}"\n', encoding="utf-8")
    config = tmp_path / "orbit-checks.yml"
    config.write_bytes(workflow)
    return runner, config, source


def test_hash_matches_raw_git_blob_reference(tmp_path):
    runner, workflow, sha = _write_case(tmp_path)
    assert len(sha) == 40
    report = check_release_guard.check(runner, workflow)
    assert report["status"] == "trusted"
    assert report["trusted_workflow"] is True
    assert report["pinned_git_blob"] == sha


def test_workflow_modification_is_blocked_even_when_steps_look_similar(tmp_path):
    runner, workflow, sha = _write_case(tmp_path)
    workflow.write_bytes(b"name: ORBIT checks\n# security-relevant modification\n")
    report = check_release_guard.check(runner, workflow)
    assert report["status"] == "blocked"
    assert report["reason"] == "workflow_pin_mismatch"
    assert not report["trusted_workflow"]
    assert report["current_workflow_git_blob"] != sha


def test_ambiguous_pin_fails_closed(tmp_path):
    runner, workflow, sha = _write_case(tmp_path)
    runner.write_text(f'TRUSTED_WORKFLOW_BLOB="{sha}"\n' * 2)
    assert check_release_guard.check(runner, workflow) == {
        "status": "blocked", "reason": "missing_or_ambiguous_pin",
        "trusted_workflow": False,
    }


def test_missing_pin_fails_closed(tmp_path):
    runner, workflow, _ = _write_case(tmp_path)
    runner.write_text("# no trusted source\n")
    assert check_release_guard.check(runner, workflow)["trusted_workflow"] is False


def test_first_mac_flight_preserves_exact_owner_trusted_workflow_pin():
    root = Path(__file__).resolve().parents[1]
    report = check_release_guard.check(
        root / "scripts" / "verify_and_launch.sh",
        root / ".github" / "workflows" / "orbit-checks.yml",
    )
    # The Node 24 CI maintenance was deliberately deferred on THIS isolated
    # Mac-first release alternative. The existing pin and workflow must match
    # byte-for-byte without changing any of the launcher's security controls.
    assert report["status"] == "trusted", report
    assert report["reason"] == "pin_matches"
    assert report["trusted_workflow"] is True
    assert report["pinned_git_blob"] == report["current_workflow_git_blob"]
    assert report["pinned_git_blob"] == "3c13b96eb6a07782be68bf1e233eb6cdae7b048d"
