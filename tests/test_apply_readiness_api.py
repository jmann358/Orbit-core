from fastapi.testclient import TestClient
from app import app

def test_apply_readiness_endpoint_stays_blocked():
    result=TestClient(app).get("/development/apply-readiness").json()
    assert result["ready"] is False
    assert result["writes_performed"] is False
    assert result["merge_performed"] is False
    assert result["owner_review_required"] is True
