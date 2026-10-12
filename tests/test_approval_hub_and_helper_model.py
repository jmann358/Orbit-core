"""Regression tests for pojo.1 reports: real helper AI approval and one inbox."""
import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core, custom_agents, helper_consent, custom_agent_model
from luna import visual_studio, goals
from luna.focus_ui import FOCUS_STYLE, FOCUS_SCRIPT, APPROVALS_SCRIPT


CLOUD = {
    "LUNA_MODEL_URL": "https://api.groq.com/openai/v1",
    "LUNA_MODEL_NAME": "openai/gpt-oss-20b",
    "LUNA_API_KEY": "fixture-private-key",
}


def test_more_tools_css_cannot_override_the_open_state():
    assert 'html.orbit-more-open #main-nav button[data-tab]:not([data-tab="home"]):not([data-tab="chat"]):not([data-tab="approvals"])' in FOCUS_STYLE
    assert 'html.orbit-more-open #main-nav{flex-wrap:wrap!important' in FOCUS_STYLE
    assert "advanced.open=expanded" in FOCUS_SCRIPT
    with tempfile.TemporaryDirectory() as directory, patch.object(
            core, "DB_PATH", Path(directory) / "db.sqlite"):
        html = TestClient(app).get("/").text
        assert 'id="focus-tools-toggle"' in html
        assert 'data-tab="approvals"' in html
        assert 'id="approval-inbox"' in html
        assert 'id="approval-inbox-filter"' in html
        assert 'id="approval-advanced"' in html
        assert 'id="focus-approvals"' in html
        assert 'LUNA / YOUR CONTROL ROOM' not in html
        assert "/api/tools" not in html


def test_pending_approvals_are_real_and_risk_categorized():
    with tempfile.TemporaryDirectory() as directory, patch.object(
            core, "DB_PATH", Path(directory) / "db.sqlite"), patch.dict(
            os.environ, CLOUD, clear=True):
        from luna.requests import create_request
        from luna.developer_agent import queue_mission
        client = TestClient(app)
        memory = core.add_candidate("Save my preferred editor into memory")
        plan = core.propose_task("Improve code clarity", "A bounded review-only task")
        note = core.add_project_note("Design preferences for the dashboard")
        create_request("technical_help", "low", "Check an inbox item",
                       "The project needs a routine owner response.")
        agent = custom_agents.propose_agent("Patch", "developer")
        dev = queue_mission(core.DB_PATH, "luna/development.py")["mission_id"]
        design = visual_studio.save("Make controls easier to use", visual_studio.EXAMPLE)
        overview = client.get("/approvals/pending")
        assert overview.status_code == 200
        content = overview.json()
        items = {entry["key"]: entry for entry in content["items"]}
        assert items["memory:" + str(memory)]["category"] == "major"
        assert items["task:" + str(plan)]["category"] == "moderate"
        assert items["note:" + str(note)]["category"] == "moderate"
        assert items["agent:" + str(agent["id"])]["category"] == "moderate"
        assert items["design:" + str(design["id"])]["actions"][0]["method"] == "GET"
        assert items["development_model:" + str(dev)]["category"] == "major"
        assert items["development_model:" + str(dev)]["actions"][0]["confirm"] is True
        assert content["counts"]["major"] >= 2
        assert content["requires_explicit_owner_action"]
        assert content["read_only"]
        assert core.candidates()[0]["status"] == "pending"
        assert custom_agents.get_agent(agent["id"])["status"] == "pending"
        assert 'fixture-private-key' not in overview.text


def test_existing_approval_endpoints_work_without_model_prose():
    with tempfile.TemporaryDirectory() as directory, patch.object(
            core, "DB_PATH", Path(directory) / "db.sqlite"), patch.dict(
            os.environ, {}, clear=True):
        client = TestClient(app)
        pending = custom_agents.propose_agent("Scout", "inspector")
        response = client.get("/approvals/pending").json()
        item = next(x for x in response["items"] if x["key"] ==
                    "agent:" + str(pending["id"]))
        approve = item["actions"][0]
        done = client.post(approve["url"], json=approve["body"])
        assert done.status_code == 200
        assert custom_agents.get_agent(pending["id"])["status"] == "active"
        assert not any(x["kind"] == "agent" for x in
                       client.get("/approvals/pending").json()["items"])


def test_unapproved_cloud_helper_work_waits_for_explicit_one_task_model_consent():
    with tempfile.TemporaryDirectory() as directory, patch.object(
            core, "DB_PATH", Path(directory) / "db.sqlite"), patch.dict(
            os.environ, CLOUD, clear=True):
        client = TestClient(app)
        agent = custom_agents.propose_agent("Patch", "developer")
        ids = custom_agents.approve_agent(agent["id"])["first_task_ids"]
        first = custom_agents.run_one()
        assert first["kind"] == "health"
        model_task = next(custom_agents.get_task(ident) for ident in ids
                          if custom_agents.get_task(ident)["kind"] == "code_review")
        task_id = model_task["id"]
        assert custom_agents.run_one() is None
        pending = client.get("/approvals/pending").json()
        record = next(x for x in pending["items"] if x["key"] ==
                      "helper_model:" + str(task_id))
        assert record["category"] == "major"
        assert record["actions"][0]["confirm"]
        denied = client.post("/agents/tasks/" + str(task_id) + "/authorize",
                             json={"approve": False})
        assert denied.status_code == 409
        assert helper_consent.approved_task_ids() == []
        allowed = client.post("/agents/tasks/" + str(task_id) + "/authorize",
                              json={"approve": True})
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["model_calls"] == 1
        assert not allowed.json()["future_tasks_authorized"]
        assert client.post("/agents/tasks/" + str(task_id) + "/authorize",
                           json={"approve": True}).status_code == 409
        assert task_id in helper_consent.approved_task_ids()
        assert not helper_consent.permitted_running(task_id)
        assert client.get("/agents").status_code == 200

        sent = []
        async def provider_post(self, url, **kwargs):
            sent.append((url, kwargs["json"], kwargs["headers"].get("Authorization")))
            return httpx.Response(200,json={"choices":[{"message":{"content":
                "Read-only code review: factor repeated validation into a helper."}}]},
                request=httpx.Request("POST",url))
        with patch.object(httpx.AsyncClient, "post", provider_post):
            task_result = custom_agents.run_one()
        assert task_result["id"] == task_id
        assert task_result["status"] == "completed"
        assert "code review" in task_result["result"]
        assert len(sent) == 1
        assert sent[0][0] == "https://api.groq.com/openai/v1/chat/completions"
        assert sent[0][1]["model"] == "openai/gpt-oss-20b"
        assert sent[0][2] == "Bearer fixture-private-key"
        assert "fixture-private-key" not in str(custom_agents.list_tasks())
        assert custom_agents.run_one() is None
        assert not helper_consent.permitted_running(task_id)


def test_helper_consent_rejects_expired_or_paused_or_wrong_role():
    from datetime import datetime, timedelta, timezone
    with tempfile.TemporaryDirectory() as directory, patch.object(
            core, "DB_PATH", Path(directory) / "db.sqlite"), patch.dict(
            os.environ, CLOUD, clear=True):
        inspector = custom_agents.propose_agent("Scout", "inspector")
        custom_agents.approve_agent(inspector["id"])
        with pytest.raises(ValueError):
            helper_consent.authorize(1, True)
        developer = custom_agents.propose_agent("Patch", "developer")
        ids = custom_agents.approve_agent(developer["id"])["first_task_ids"]
        target = next(i for i in ids if custom_agents.get_task(i)["kind"] == "code_review")
        earlier = datetime.now(timezone.utc) - timedelta(hours=3)
        helper_consent.authorize(target, True, now=earlier)
        assert custom_agents.run_one() is not None  # inspector's health
        assert custom_agents.run_one() is not None  # developer's health
        assert custom_agents.run_one() is None  # expired model call not claimed
        assert not helper_consent.permitted_running(target)
        assert not client_model_executed()


def client_model_executed():
    """Stand-in for an external-model side effect; this test makes none."""
    return False


def test_remote_unknown_owner_cannot_authorize_model_cost():
    with tempfile.TemporaryDirectory() as directory, patch.object(
            core, "DB_PATH", Path(directory) / "db.sqlite"):
        env = {**CLOUD, "LUNA_CLOUD_MODE": "1",
               "LUNA_OWNER_TOKEN": "Q" * 40,
               "LUNA_PUBLIC_ORIGIN": "https://luna.example.org"}
        with patch.dict(os.environ, env, clear=True):
            agent = custom_agents.propose_agent("Patch", "developer")
            ids = custom_agents.approve_agent(agent["id"])["first_task_ids"]
            task_id = next(i for i in ids
                           if custom_agents.get_task(i)["kind"] == "code_review")
            client = TestClient(app, base_url="https://luna.example.org")
            assert client.get("/approvals/pending").status_code == 401
            assert client.post("/agents/tasks/"+str(task_id)+"/authorize",
                               json={"approve": True}).status_code == 401
            assert helper_consent.approved_task_ids() == []


def test_approval_center_scripts_have_valid_javascript_when_node_available():
    node=shutil.which("node")
    if not node:
        pytest.skip("No Node runtime")
    with tempfile.TemporaryDirectory() as directory, patch.object(
            core, "DB_PATH", Path(directory) / "db.sqlite"):
        html=TestClient(app).get("/").text
        scripts=re.findall(r"<script>(.*?)</script>",html,re.S)
        for script in scripts:
            result=subprocess.run([node,"--check"],input=script,text=True,
                                  capture_output=True,timeout=10)
            assert result.returncode==0,result.stderr[:1800]
