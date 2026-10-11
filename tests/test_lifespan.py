from fastapi.testclient import TestClient
from app import app

def test_lifespan_starts_and_stops_workers_without_legacy_event_hooks():
    assert app.router.on_startup==[]
    assert app.router.on_shutdown==[]
    with TestClient(app) as client:
        response=client.get("/version")
        assert response.status_code==200
        assert response.json()["version"]=="1.1.2.3.5.8.13.21"
