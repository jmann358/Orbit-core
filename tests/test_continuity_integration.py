import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core,continuity

def test_sessions_endpoint_returns_meaningful_title():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"sessions.db"):
            core.add_message("named","user","Plan the next ORBIT memory retrieval milestone")
            core.add_message("named","assistant","Ready.")
            response=TestClient(app).get("/sessions")
            assert response.status_code==200
            item=response.json()[0]
            assert item["session"]=="named"
            assert item["title"].startswith("Plan the next ORBIT")
            assert item["message_count"]==2

def test_chat_creates_pending_checkpoint_after_eight_safe_user_messages():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"chat.db"):
            client=TestClient(app)
            last=None
            for i in range(8):
                last=client.post("/chat",json={
                    "session":"long-chat",
                    "message":"ORBIT continuity planning message "+str(i)+" about memory retrieval"
                })
                assert last.status_code==200
            checkpoint=last.json()["continuity_checkpoint"]
            assert checkpoint["created"] is True
            pending=continuity.list_summaries("pending")
            assert len(pending)==1
            assert pending[0]["session"]=="long-chat"
            assert continuity.approved_context("memory retrieval")==[]

def test_dashboard_contains_continuity_controls():
    response=TestClient(app).get("/")
    assert response.status_code==200
    html=response.text
    assert 'id="continuity-refresh"' in html
    assert 'id="continuity-search-form"' in html
    assert "Approve for Luna" in html


def test_dashboard_has_one_continuity_handler_and_main_review_wiring():
    response=TestClient(app).get("/")
    assert response.status_code==200
    html=response.text
    assert html.count("async function refreshContinuity()")==1
    assert "Conversation checkpoint" in html
    assert "Revoke from Luna" in html
    assert "data.counts.continuity" in html
