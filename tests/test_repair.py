from luna.repair import RepairState, advance, rollback_plan

def test_repair_requires_isolation_and_permission():
    assert advance(RepairState(),tests_passed=True,isolation_verified=False,permission_valid=True).status=="needs_attention"
    assert advance(RepairState(),tests_passed=True,isolation_verified=True,permission_valid=False).status=="needs_attention"

def test_repair_stops_after_two_attempts():
    state=advance(RepairState(base_sha256="base"),tests_passed=False,isolation_verified=True,permission_valid=True)
    assert state.status=="retry_allowed" and state.attempts==1
    state=advance(state,tests_passed=False,isolation_verified=True,permission_valid=True)
    assert state.status=="needs_attention" and state.attempts==2
    assert rollback_plan(state)["executed"] is False

def test_passing_repair_still_requires_review():
    state=advance(RepairState(),tests_passed=True,isolation_verified=True,permission_valid=True)
    assert state.status=="ready_for_review"
    try:
        advance(state,tests_passed=True,isolation_verified=True,permission_valid=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Terminal repair must not advance")
