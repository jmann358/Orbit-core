import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core

def _seed():
    core.add_message("session-a","user","We discussed keeping ORBIT local first.")
    core.add_message("session-a","assistant","Got it.")

def test_continuity_api_review_and_search():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity-api.db"):
            _seed()
            client=TestClient(app)
            created=client.post("/continuity/summaries",json={
                "session":"session-a",
                "summary":"ORBIT should remain local first while cloud services stay optional and reviewable.",
                "tags":["orbit","architecture"],
            })
            assert created.status_code==200
            summary_id=created.json()["id"]

            pending=client.get("/continuity/summaries",params={"status":"pending"})
            assert pending.status_code==200
            assert pending.json()[0]["id"]==summary_id

            approved=client.post(
                f"/continuity/summaries/{summary_id}/decision",
                json={"approve":True})
            assert approved.status_code==200
            assert approved.json()["status"]=="approved"

            search=client.get("/continuity/search",params={"q":"ORBIT local"})
            assert search.status_code==200
            assert search.json()[0]["session"]=="session-a"

            status=client.get("/continuity/status")
            assert status.status_code==200
            assert status.json()["approved"]==1

def test_continuity_search_rejects_too_short_query():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity-api.db"):
            client=TestClient(app)
            response=client.get("/continuity/search",params={"q":"x"})
            assert response.status_code==400


def test_continuity_sessions_and_memory_ui():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity-api.db"):
            _seed()
            client=TestClient(app)
            sessions=client.get("/continuity/sessions")
            assert sessions.status_code==200
            assert sessions.json()[0]["session"]=="session-a"
            assert sessions.json()[0]["message_count"]==2

    html=TestClient(app).get("/").text
    assert 'id="continuity-list"' in html
    assert 'id="continuity-search-form"' in html
    assert "refreshContinuity()" in html
    assert "v1.1.2.3.5.8" in html
