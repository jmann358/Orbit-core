from fastapi.testclient import TestClient
from app import app

def test_autonomy_cycle_endpoint_is_review_only():
    result=TestClient(app).post("/development/autonomy-cycle").json()
    assert result["state"]=="prepared"
    assert result["task_id"]=="DEV-002"
    assert result["authority"]=="review_only"
    assert result["requires_verification"] is True
    assert result["requires_review"] is True
    assert result["may_apply_code"] is False
    assert result["may_merge"] is False
    assert result["may_expand_permissions"] is False
