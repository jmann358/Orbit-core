"""Acceptance coverage for Luna's uncluttered, real-data home screen."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import app
from luna import attention_feed, core, visual_studio


def empty_snapshot():
    return {"requests": [], "tasks": [], "improvements": [], "drafts": [],
            "notes": [], "memories": [],
            "counts": {"bridge": 0, "queued_jobs": 0, "attention_jobs": 0}}


def empty_activity():
    return {"recent": [], "status": "Idle"}


def model(state="configured_unverified"):
    return {"state": state, "detail": "Model settings are present."}


def test_high_priority_owner_request_highlights_single_next_action():
    overview = empty_snapshot()
    overview["requests"] = [
        {"id": 8, "title": "A quick decision", "message": "What should I change?",
         "priority": "high"},
        {"id": 7, "title": "Routine request", "message": "Review this later",
         "priority": "low"},
    ]
    overview["notes"] = [{"id": 3, "content": "A project idea", "status": "pending"}]
    summary = attention_feed.summarize(overview, empty_activity(), model("not_configured"))
    assert summary["next"]["title"] == "A quick decision"
    assert summary["next"]["id"] == 8
    assert summary["next"]["action"] == "review"
    assert "not execute code" in summary["next"]["why"]
    assert summary["waiting_count"] == 4  # two requests, one note, missing model
    assert summary["read_only"] and summary["approval_required"]


def test_failed_work_is_important_but_not_mistaken_for_completed():
    overview = empty_snapshot()
    activity = {
        "recent": [
            {"id": 2, "title": "GitHub status", "state": "completed", "result": "Passed",
             "created_at": "2026-10-11T19:00:00Z"},
            {"id": 3, "title": "Plan review", "state": "attention", "result": "Stopped",
             "created_at": "2026-10-11T20:00:00Z"},
            {"id": 4, "title": "Check updates", "state": "queued", "result": "",
             "created_at": "2026-10-11T21:00:00Z"},
        ]
    }
    summary = attention_feed.summarize(overview, activity, model("not_configured"))
    assert summary["next"]["action"] == "activity"
    assert summary["next"]["kind"] == "work"
    assert summary["work"]["queued"] == 1
    assert summary["work"]["attention"] == 1
    assert summary["work"]["completed_recent"] == 1
    assert summary["work"]["recent"][0]["title"] == "Check updates"


def test_no_tasks_is_truthful_about_model_setup():
    overview = empty_snapshot()
    unplugged = attention_feed.summarize(overview, empty_activity(), model("not_configured"))
    assert unplugged["next"]["title"] == "Connect Luna's AI model"
    assert unplugged["next"]["action"] == "chat"
    assert not unplugged["model"]["verified"]
    configured = attention_feed.summarize(overview, empty_activity(), model())
    assert configured["next"]["title"] == "Talk to Luna"
    assert "verify" in configured["next"]["explanation"].lower()
    assert configured["waiting_count"] == 0
    assert configured["work"]["completed_recent"] == 0


def test_design_and_development_review_are_visible_but_never_auto_applied():
    overview = empty_snapshot()
    designs = [{"id": 2, "status": "pending", "direction": "Simpler layout",
                "design": {"title": "Luna Moon"}}]
    missions = [{"id": 4, "state": "review", "summary": "Unapplied draft",
                 "updated_at": "2026-10-11T23:00:00Z"}]
    summary = attention_feed.summarize(overview, empty_activity(), model(),
                                       missions=missions, designs=designs)
    assert summary["next"]["action"] == "design"
    assert any(x["kind"] == "development" and x["action"] == "developer"
               for x in summary["waiting"])
    assert summary["waiting_count"] == 2
    assert "no generated" not in summary["next"]["why"]  # truthful specific phrasing


def test_dashboard_opens_on_focus_and_retains_all_original_controls():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "db.sqlite"):
            client = TestClient(app)
            html = client.get("/").text
            assert "One thing at a time." in html
            assert 'id="focus-primary"' in html
            assert 'id="focus-why"' in html
            assert 'title="Why Luna recommends this"' in html
            assert 'aria-describedby="focus-explanation"' in html
            assert 'id="focus-waiting"' in html
            assert 'id="focus-recent"' in html
            assert 'id="focus-tools-toggle"' in html
            assert "selectTab('home');" in html
            assert "selectTab(localStorage.getItem('luna-active-tab')||'chat')" not in html
            assert 'id="control-review"' in html
            assert 'id="control-autopilot"' in html
            assert 'id="tab-home" class="tab-panel active"' in html  # visible before scripts run
            assert html.count('class="tab-panel active"') == 1
            assert 'id="tab-development"' in html
            assert 'id="tab-testing"' in html
            assert 'id="tab-memory"' in html
            assert "/focus/summary" in html
            assert 'data-review-kind' not in html  # created safely at runtime, not fake HTML


def test_readonly_summary_shows_real_saved_decisions_and_model_status():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "focus.db"):
            with patch.dict(os.environ, {"LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
                                         "LUNA_MODEL_NAME": "local-test"}, clear=True):
                client = TestClient(app)
                task_id = core.propose_task("Fix layout", "Review simpler dashboard")
                memory_id = core.add_candidate("Remember Luna should feel simpler")
                first = client.get("/focus/summary")
                assert first.status_code == 200, first.text
                data = first.json()
                assert data["next"]["kind"] == "task"
                assert data["next"]["id"] == task_id
                assert data["waiting_count"] == 2
                assert data["model"]["state"] == "configured_unverified"
                assert data["model"]["verified"] is False
                assert not data["polling_is_not_work"] is False
                assert any(item["id"] == memory_id for item in data["waiting"])
                assert next(t for t in core.list_tasks() if t["id"] == task_id)["status"] == "pending"
                assert next(m for m in core.candidates() if m["id"] == memory_id)["status"] == "pending"
                assert client.post("/autonomy/tasks/" + str(task_id) + "/decision",
                                   json={"decision": "approved"}).status_code == 200
                later = client.get("/focus/summary").json()
                assert later["next"]["kind"] == "memory"


def test_focused_visual_theme_uses_existing_more_tools_not_a_second_button():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "focus.db"):
            design = visual_studio.save("Simple navigation with rounded corners", visual_studio.EXAMPLE)
            visual_studio.approve(design["id"])
            html = TestClient(app).get("/").text
            assert html.count('id="focus-tools-toggle"') == 1
            assert 'id="visual-more-tools"' not in html
            assert 'class="visual-focus"' in html
            assert "visual-show-all" in html
            assert 'id="visual-studio-theme"' in html


def test_frontend_uses_text_content_no_generated_html_injection():
    from luna.focus_ui import FOCUS_SCRIPT
    assert "innerHTML" not in FOCUS_SCRIPT
    assert ".textContent" in FOCUS_SCRIPT
    assert "next.why" in FOCUS_SCRIPT
    assert "focus-target-review" in FOCUS_SCRIPT
    assert "await loadControl()" in FOCUS_SCRIPT


def test_embedded_focus_javascript_is_parseable_when_node_available():
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node runtime is not installed")
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "db.sqlite"):
            html = TestClient(app).get("/").text
            scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
            assert scripts
            for code in scripts:
                result = subprocess.run([node, "--check"], input=code,
                                        capture_output=True, text=True,
                                        timeout=10, check=False)
                assert result.returncode == 0, result.stderr[:1600]
