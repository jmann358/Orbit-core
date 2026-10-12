"""Release identifier used in the dashboard and API must agree."""
from fastapi.testclient import TestClient
from app import app, VERSION


def test_luna_pojo_release_identifier_is_consistent():
    assert VERSION == "pojo.1"
    assert app.title == "ORBIT · Luna pojo.1"
    client = TestClient(app)
    response = client.get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "pojo.1"
    assert payload["build"] == "pojo.1"

    home = client.get("/")
    assert home.status_code == 200
    assert "<title>Luna pojo.1 · ORBIT</title>" in home.text
    assert "<small>pojo.1 · Agent Core</small>" in home.text
    assert "v1.0.0-rc.1" not in home.text
