import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from luna import core
from luna.development import normalize_tasks, planning_report, static_draft_report


def test_shared_task_registry_does_not_trust_remote_authority():
    tasks = normalize_tasks({"schema_version": 1, "tasks": [
        {"id": "DEV-001", "execution": "read_only", "title": "Check"},
        {"id": "DEV-999", "execution": "shell", "title": "Run shell"},
        {"id": "DEV-002", "execution": "shell", "title": "Wrong capability"},
        {"id": "DEV-003", "execution": "planning_only", "title": "Plan"},
    ]})
    assert [t["eligible"] for t in tasks] == [True, False, False, True]
    with pytest.raises(ValueError):
        normalize_tasks({"schema_version": 1, "tasks": [
            {"id": "DEV-001"}, {"id": "DEV-001"}]})


def test_static_review_only_parses_python_blocks():
    result = static_draft_report("Example:\n```python\nx = 1\n```")
    assert result["all_checked_blocks_parse"]
    assert not result["executed"]
    assert not result["applied"]
    broken = static_draft_report("```python\nif :\n```")
    assert not broken["all_checked_blocks_parse"]
    assert not static_draft_report("No code block")["all_checked_blocks_parse"]


def test_planning_reports_are_fixed_and_read_only():
    assert "AST" in planning_report("DEV-002")
    assert "pause" in planning_report("DEV-003")
    with pytest.raises(ValueError):
        planning_report("DEV-999")


def test_shared_task_results_are_persistent_and_validated():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "tasks.db"):
            result_id = core.record_shared_task("DEV-002", "completed", "Safe plan")
            records = core.list_shared_task_results()
            assert records[0]["id"] == result_id
            assert records[0]["summary"] == "Safe plan"
            with pytest.raises(ValueError):
                core.record_shared_task("DEV-999", "completed", "Bad task")


def test_project_inventory_is_metadata_only_and_fixed_scope():
    from luna.development import project_inventory, INSPECTION_FILES
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "app.py").write_text("hello")
        (root / ".env").write_text("SECRET=do-not-read")
        report = project_inventory(root)
        assert report["present_count"] == 1
        assert not report["tests_run"]
        assert not report["capabilities_verified"]
        assert {x["path"] for x in report["files"]} == set(INSPECTION_FILES)
        assert next(x for x in report["files"] if x["path"] == "app.py")["bytes"] == 5
        assert ".env" not in str(report)


def test_control_overview_and_review_are_non_executing():
    from fastapi.testclient import TestClient
    from app import app
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "control.db"):
            client = TestClient(app)
            initial = client.get("/control/overview")
            assert initial.status_code == 200
            assert initial.json()["auto_apply"] is False
            assert initial.json()["inventory"]["tests_run"] is False
            created = client.post("/control/suggest-next")
            assert created.status_code == 200
            proposal = created.json()["proposal"]
            assert proposal and created.json()["code_changed"] is False
            refreshed = client.get("/control/overview").json()
            assert refreshed["counts"]["improvements"] == 1
            reviewed = client.post(
                f"/control/improvements/{proposal['id']}/decision",
                json={"decision": "approved"})
            assert reviewed.status_code == 200
            assert reviewed.json()["applied"] is False
            assert client.get("/control/overview").json()["counts"]["improvements"] == 0
            assert client.post(
                f"/control/improvements/{proposal['id']}/decision",
                json={"decision": "approved"}).status_code == 409


def test_static_review_rejects_incomplete_screening():
    draft = "\n".join("```python\nx = %d\n```" % n for n in range(13))
    result = static_draft_report(draft)
    assert result["python_blocks_found"] == 13
    assert result["blocks_checked"] == 12
    assert result["truncated"] is True
    assert result["all_checked_blocks_parse"] is False
    assert result["executed"] is False
    assert result["applied"] is False
