"""Additional safe capability drafting never broadens privileged source access."""
from pathlib import Path
import tempfile

import pytest

from luna.developer_agent import TEMPLATES, queue_mission
from luna.patches import ALLOWED_PATHS
from luna.developer_api import STUDIO_HTML


def test_developer_agent_only_targets_six_reviewable_low_risk_modules():
    assert set(TEMPLATES) == set(ALLOWED_PATHS)
    assert set(TEMPLATES) == {
        "luna/development.py",
        "luna/self_improvement.py",
        "luna/presentation.py",
        "luna/proactive.py",
        "luna/skill_catalog.py",
        "luna/goal_recipes.py",
    }
    assert all("owner" in text.lower() or "without" in text.lower()
               for text in TEMPLATES.values())
    for forbidden in (
        "app.py", "luna/core.py", "luna/model_connection.py",
        "luna/cloud_security.py", "luna/permissions.py",
        "luna/launch_guard.py", "luna/github_auth.py",
        "luna/self_build.py", ".env",
    ):
        assert forbidden not in ALLOWED_PATHS


def test_agent_studio_offers_new_safe_tasks_without_unlocking_unsafe_files():
    for path in ALLOWED_PATHS:
        assert 'value="' + path + '"' in STUDIO_HTML
    assert 'value="app.py"' not in STUDIO_HTML
    assert 'value="luna/core.py"' not in STUDIO_HTML


def test_queue_new_review_only_target_never_runs_or_writes_source():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        database = root / "queue.db"
        queued = queue_mission(database, "luna/proactive.py")
        assert queued["created"]
        assert not (root / "luna").exists()
        with pytest.raises(ValueError):
            queue_mission(database, "luna/permissions.py")
