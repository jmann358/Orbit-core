import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from luna import core
from app import app

def test_memory_review_end_to_end_without_model_calls():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"test.db"):
            client=TestClient(app)
            settings=client.get("/memory/suggestions/settings").json()
            assert settings["enabled"] is False
            assert client.post("/memory/suggestions/settings",json={"enabled":True}).status_code==200
            # Explicit chat command uses local job routing, avoiding a model request.
            response=client.post("/chat",json={"session":"test","message":"Remember that ORBIT should remain local first"})
            assert response.status_code==200
            items=client.get("/memory/candidates").json()
            assert len(items)==1 and items[0]["status"]=="pending"
            assert core.approved_memories()==[]
            result=client.post("/memory/candidates/"+str(items[0]["id"])+"/review?approve=true")
            assert result.status_code==200
            assert core.approved_memories()==["ORBIT should remain local first"]

def test_saved_draft_quality_endpoint_does_not_apply_code():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"test.db"):
            draft_id=core.save_code_draft("Improve memory","Review me","File modified: luna/core.py\n```diff\n+ if role in (\"user\", \"assistant\"):\n+     add_candidate(message)\n```")
            result=TestClient(app).get("/project/drafts/"+str(draft_id)+"/quality")
            assert result.status_code==200
            report=result.json()
            assert report["status"]=="needs_revision"
            assert report["applied"] is False and report["executed"] is False
