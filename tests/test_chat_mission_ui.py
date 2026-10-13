"""Chat contextual mission card is a view of existing persisted work only."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core, goals, jobs


def test_chat_renders_one_contextual_saved_goal_card_with_existing_gate(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "chat-card.sqlite"):
        client = TestClient(app)
        html = client.get("/").text
        assert html.count('id="chat-mission-card"') == 1
        assert html.count('id="chat-mission-details"') == 1
        assert 'id="chat-mission-state" role="status"' in html
        assert 'async function refreshChatMissionCard' in html
        assert "'/agent/goals/'+g.id+'/report'" in html
        assert "act('/decision',{approve,...identity(plan)})" in html
        assert "'/agent/goals/'+plan.id+'/view'" in html
        assert "Approve listed steps" in html
        assert "Reject plan" in html
        assert "The saved plan may have changed" in html
        assert "if(holder._missionBusy)return;" in html
        assert "No paid calls, new access" in html
        assert "if(window.refreshChatMissionCard)window.refreshChatMissionCard();" in html
        assert 'id="log"' in html


def test_chat_card_does_not_auto_approve_or_create_work_on_page_load(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "chat-proposal.sqlite"):
        goal_id = goals.propose_goal("Check safe local project health", ["project_health"])
        client = TestClient(app)
        before = client.get(f"/agent/goals/{goal_id}/report").json()
        assert before["state"] == "proposed"
        assert all(step["job_id"] is None for step in before["steps"])
        for _ in range(3):
            assert client.get("/").status_code == 200
            assert client.get("/agent/goals").status_code == 200
        after = client.get(f"/agent/goals/{goal_id}/report").json()
        assert after["state"] == "proposed"
        assert all(step["job_id"] is None for step in after["steps"])
        assert jobs.list_jobs() == []


def test_existing_owner_goal_decision_prevents_replay_from_old_card(tmp_path):
    with patch.object(core, "DB_PATH", tmp_path / "chat-stale.sqlite"):
        goal_id = goals.propose_goal("Inspect project status safely", ["project_health"])
        client = TestClient(app)
        first = client.post(f"/agent/goals/{goal_id}/decision", json=approval_payload(client, goal_id, False))
        assert first.status_code == 200
        stale = client.post(f"/agent/goals/{goal_id}/decision", json=approval_payload(client, goal_id, True))
        assert stale.status_code != 200
        report = client.get(f"/agent/goals/{goal_id}/report").json()
        assert report["state"] == "rejected"
        assert all(step["job_id"] is None for step in report["steps"])


def approval_payload(client, ident, approve):
    displayed = client.get(f"/agent/goals/{ident}/report").json()
    return {"approve": approve, "expected_revision": displayed["revision"],
            "expected_digest": displayed["plan_digest"]}
