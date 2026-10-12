"""Product launch acceptance checks: local-only, read-only, and no credential leaks."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("luna_starter", ROOT / "scripts" / "start_luna.py")
starter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(starter)


def test_launcher_is_localhost_only():
    command = starter.server_command()
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "8000"
    assert "--reload" not in command


def test_readiness_uses_flags_not_credentials():
    with patch.dict("os.environ", {
        "LUNA_MODEL_URL": "https://private.example/",
        "LUNA_MODEL_NAME": "private-model",
        "LUNA_API_KEY": "SECRET-NEVER-PRINT",
    }):
        text = json.dumps(starter.readiness())
    assert "SECRET-NEVER-PRINT" not in text
    assert "https://private.example/" not in text
    assert "private-model" not in text
    report = json.loads(text)
    assert report["remote_phone_access_enabled"] is False
    assert report["model_name_configured"] is True


def test_readiness_is_non_mutating(tmp_path, capsys):
    with patch.object(starter, "ROOT", tmp_path):
        with patch("os.chdir") as change_directory:
            with patch.object(starter, "REQUIRED", ()):
                assert starter.main(["--check"]) == 0
            change_directory.assert_not_called()
    report = json.loads(capsys.readouterr().out)
    assert report["missing_dependencies"] == []
    assert report["dashboard_url"] == "http://127.0.0.1:8000"
    assert list(tmp_path.iterdir()) == []


def test_dashboard_starts_with_only_one_visible_panel():
    from fastapi.testclient import TestClient
    from app import app
    html = TestClient(app).get("/").text
    assert 'id="tab-chat" class="tab-panel active"' in html
    assert html.count('class="tab-panel active"') == 1
