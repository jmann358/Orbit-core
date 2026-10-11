import pytest
from luna.development_relay import build_report, luna_view

SHA = "a" * 40


def test_passed_report_has_no_execution_authority():
    report = build_report(
        commit_sha=SHA,
        result="passed",
        checks={"tests": True, "syntax": True},
    )
    assert report["may_apply_code"] is False
    assert report["may_merge"] is False
    assert report["may_expand_permissions"] is False
    assert luna_view(report)["authority"] == "verification_only"


def test_blocked_report_preserves_security_gate():
    report = build_report(
        commit_sha=SHA,
        result="blocked",
        checks={"tests": True, "security": False},
        blocked_gates=("security",),
    )
    assert report["blocked_gates"] == ["security"]


@pytest.mark.parametrize("sha", ["abc", "G" * 40, "a" * 39])
def test_rejects_invalid_commit_sha(sha):
    with pytest.raises(ValueError):
        build_report(commit_sha=sha, result="passed", checks={"tests": True})


def test_rejects_unknown_checks_and_authority_smuggling():
    with pytest.raises(ValueError):
        build_report(commit_sha=SHA, result="passed", checks={"run_shell": True})
    with pytest.raises(ValueError):
        build_report(
            commit_sha=SHA,
            result="passed",
            checks={"tests": True},
            blocked_gates=("security",),
        )
