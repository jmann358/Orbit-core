from luna.apply_gate import evaluate
from luna.change_guard import prepare_checkpoint
from luna.repair import RepairState

def test_apply_gate_requires_every_safety_condition():
    checkpoint=prepare_checkpoint("luna/development.py","a"*64,"b"*64)
    state=RepairState(attempts=1,status="ready_for_review",
                      base_sha256="a"*64,candidate_sha256="b"*64)
    result=evaluate("luna/development.py",state,checkpoint,
                    isolation_enabled=True,apply_permission=True)
    assert result["ready"] is True
    assert result["writes_performed"] is False
    assert result["merge_performed"] is False
    assert result["rollback_required"] is True
    assert result["owner_review_required"] is True

def test_apply_gate_fails_closed_without_permission():
    checkpoint=prepare_checkpoint("luna/development.py","a"*64,"b"*64)
    state=RepairState(attempts=1,status="ready_for_review")
    assert evaluate("luna/development.py",state,checkpoint,
                    isolation_enabled=True,apply_permission=False)["ready"] is False
