from fastapi.testclient import TestClient
from app import app

def test_sprint_status_is_read_only_and_disabled():
    response=TestClient(app).get("/control/sprint")
    assert response.status_code==200
    data=response.json()
    assert not data["runner"]["isolated_tests_enabled"]
    assert not data["sprint"]["autonomous_code_apply_enabled"]
    assert len(data["sprint"]["stages"])==6

def test_sprint_tab_renders():
    html=TestClient(app).get("/").text
    assert 'data-tab="sprint"' in html
    assert 'id="sprint-stages"' in html
    assert 'id="sprint-gates"' in html
    assert "refreshSprint()" in html
