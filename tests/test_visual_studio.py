"""The visual editor must preview and require explicit owner approval."""
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core, visual_studio


def test_design_preview_requires_approval_and_can_be_undone():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "design.sqlite"):
            client = TestClient(app)
            assert '/design' in client.get("/").text
            assert 'sandbox=""' in client.get("/design").text
            assert 'visual-studio-theme' not in client.get("/").text
            # Unit tests must never call a real provider.
            with patch("luna.visual_studio_api.respond", new_callable=AsyncMock,
                       return_value="Luna's memory is working, but no AI model is connected"):
                response = client.post("/design/proposals", json={"direction": "Simplify my home screen."})
                assert response.status_code == 503
            proposed = visual_studio.save("Make it simple and purple", visual_studio.EXAMPLE)
            pid = proposed["id"]
            assert proposed["status"] == "pending"
            assert visual_studio.active() is None
            assert 'visual-studio-theme' not in client.get("/").text
            preview = client.get("/?design_preview=" + str(pid))
            assert preview.status_code == 200
            assert 'visual-studio-theme' in preview.text
            assert "#384FB5" in preview.text
            assert 'visual-focus' in preview.text
            assert "visual-more-tools" in preview.text
            assert visual_studio.active() is None
            assert client.post("/design/proposals/" + str(pid) + "/approve").status_code == 200
            assert visual_studio.active()["id"] == pid
            assert 'visual-studio-theme' in client.get("/").text
            assert client.post("/design/proposals/" + str(pid) + "/approve").status_code == 409
            assert client.post("/design/reset").json()["original_restored"] is True
            assert visual_studio.active() is None
            assert 'visual-studio-theme' not in client.get("/").text
            assert client.post("/design/proposals/" + str(pid) + "/restore").status_code == 200
            assert visual_studio.active()["id"] == pid


def test_model_generates_preview_and_supports_refinement():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "design.sqlite"):
            with patch("luna.visual_studio_api.respond", new_callable=AsyncMock,
                       return_value=json.dumps(visual_studio.EXAMPLE)) as model:
                client = TestClient(app)
                initial = client.post("/design/proposals", json={
                    "direction": "Make the dashboard less cluttered."})
                assert initial.status_code == 200, initial.text
                first = initial.json()
                assert first["status"] == "pending"
                assert first["design"]["title"] == "Moonlight Workspace"
                assert visual_studio.active() is None
                refinement = client.post("/design/proposals", json={
                    "direction": "Try darker colors.", "base_design_id": first["id"]})
                assert refinement.status_code == 200, refinement.text
                assert refinement.json()["id"] != first["id"]
                assert "Start from this earlier design" in model.await_args.args[1]
                assert visual_studio.active() is None
                assert client.post("/design/proposals/" + str(first["id"]) + "/reject").status_code == 200
                assert client.post("/design/proposals/" + str(first["id"]) + "/approve").status_code == 409
                assert client.post("/design/proposals", json={
                    "direction": "Try something else", "base_design_id": first["id"]}).status_code == 404


def test_visual_proposals_are_data_only_accessible_and_revisioned():
    safe = visual_studio.validate_design(visual_studio.EXAMPLE)
    assert safe["navigation"] == "focused"
    assert "script" not in visual_studio.style_for(safe)
    injected = dict(safe)
    injected["colors"] = dict(safe["colors"], accent="#384FB5;body{display:none}")
    with pytest.raises(ValueError):
        visual_studio.validate_design(injected)
    poorly_contrasted = dict(safe)
    poorly_contrasted["colors"] = dict(safe["colors"], text="#FFFFFF")
    with pytest.raises(ValueError):
        visual_studio.validate_design(poorly_contrasted)
    expanded = dict(safe, extra="arbitrary CSS")
    with pytest.raises(ValueError):
        visual_studio.validate_design(expanded)
    with pytest.raises(ValueError):
        visual_studio.parse_model_design("Sure, here's some CSS...")
    with pytest.raises(ValueError):
        visual_studio.validate_design(dict(safe, max_width=True))
    assert visual_studio.parse_model_design(json.dumps(safe)) == safe


def test_invalid_model_does_not_save_or_apply_design():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "design.sqlite"):
            with patch("luna.visual_studio_api.respond", new_callable=AsyncMock,
                       return_value="Luna's memory is working, but no AI model is connected"):
                client = TestClient(app)
                response = client.post("/design/proposals", json={"direction": "Simplify the screen"})
                assert response.status_code == 503
                assert client.get("/design/status").json()["proposals"] == []
            with patch("luna.visual_studio_api.respond", new_callable=AsyncMock,
                       return_value='{"colors": "not actual CSS"}'):
                response = TestClient(app).post("/design/proposals",
                                                json={"direction": "Try a different style"})
                assert response.status_code == 422
                assert visual_studio.active() is None
