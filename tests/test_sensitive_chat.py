import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app import app
from luna import core

def test_sensitive_chat_is_not_persisted_or_sent_to_model():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"sensitive.db"):
            with patch("app.respond") as respond:
                response=TestClient(app).post("/chat",json={
                    "session":"secret-test",
                    "message":"password=supersecret123"
                })
                assert response.status_code==200
                data=response.json()
                assert data["stored"] is False
                assert data["model_called"] is False
                assert data["sensitive_intake"]["luna_may_receive"] is False
                respond.assert_not_called()
                with core.connect() as db:
                    count=db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                assert count==0
