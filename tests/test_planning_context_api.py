from fastapi.testclient import TestClient
from app import app

def test_planning_context_endpoint_validates_title():
    client=TestClient(app)
    response=client.get("/development/planning-context",params={"title":"a"})
    assert response.status_code==400

def test_planning_context_endpoint_returns_read_only_context():
    response=TestClient(app).get("/development/planning-context",params={"title":"Improve sandbox runner"})
    assert response.status_code==200
    body=response.json()
    assert body["automatic_actions"] is False
    assert body["source"]=="approved_technical_memory"

def test_sprint_dashboard_includes_memory_lookup():
    html=TestClient(app).get("/").text
    assert 'id="sprint-plan-title"' in html
    assert 'id="sprint-plan-search"' in html
    assert "searchSprintContext" in html
