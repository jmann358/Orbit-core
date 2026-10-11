import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from luna import core
from app import app


def test_luna_design_mission_creates_unapplied_draft():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "design.db"):
            with patch("app.respond", new_callable=AsyncMock, return_value="Moonlit studio: redesign navigation and colors; keep all IDs.") as model:
                response = TestClient(app).post("/project/luna-design-mission")
                assert response.status_code == 200
                data = response.json()
                assert data["applied"] is False
                assert data["requires_approval"] is True
                assert data["draft_id"] > 0
                assert "Moonlit studio" in data["draft"]
                assert "CURRENT DASHBOARD SOURCE" in model.await_args.args[1]
                assert 'id="main-nav"' in model.await_args.args[1]
                drafts = TestClient(app).get("/project/drafts").json()
                assert any(item["id"] == data["draft_id"] for item in drafts)


def test_luna_design_mission_model_unavailable():
    with patch("app.respond", new_callable=AsyncMock, return_value="Cloud AI needs configuration"):
        response = TestClient(app).post("/project/luna-design-mission")
        assert response.status_code == 503
