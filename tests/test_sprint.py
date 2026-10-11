"""Safety contract for the major development sprint."""
from luna.sprint import sprint_snapshot
from luna.runner_preflight import inspect_runner

def test_sprint_gates_are_explicit():
    data=sprint_snapshot()
    assert data["max_repair_attempts"]==2
    assert data["paid_actions_require_approval"]
    assert data["git_merges_require_approval"]
    assert not data["autonomous_code_apply_enabled"]
    assert not data["isolated_draft_execution_enabled"]
    assert {s["id"] for s in data["stages"]}=={"runner","repairs","github","memory","planning","dashboard"}

def test_runner_fails_closed_without_isolation():
    data=inspect_runner()
    assert not data["isolated_tests_enabled"]
    assert not data["draft_execution_enabled"]
    assert data["approval_required"]
