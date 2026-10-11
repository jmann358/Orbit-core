import hashlib
import tempfile
from pathlib import Path

import pytest
from luna.workshop import stage


def test_workshop_compiles_in_temporary_workspace_without_live_changes():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        (root/"luna").mkdir()
        target=root/"luna/development.py"
        target.write_text("VALUE = 1\n")
        original=target.read_bytes()
        sha=hashlib.sha256(original).hexdigest()
        result=stage(root,"luna/development.py",sha,"VALUE = 2\n")
        assert result["bytecode_compiles"]
        assert result["workspace_deleted"]
        assert result["checkpoint"]["automatic_restore"] is False
        assert result["checkpoint"]["requires_review"] is True
        assert not result["tests_executed"]
        assert not result["draft_executed"]
        assert not result["live_files_changed"]
        assert target.read_bytes()==original


def test_workshop_rejects_stale_revisions_and_unsafe_targets():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        (root/"luna").mkdir()
        target=root/"luna/development.py"
        target.write_text("VALUE = 1\n")
        sha=hashlib.sha256(target.read_bytes()).hexdigest()
        with pytest.raises(ValueError):
            stage(root,"luna/development.py","0"*64,"VALUE = 2\n")
        with pytest.raises(ValueError):
            stage(root,"app.py",sha,"VALUE = 2\n")
        with pytest.raises(ValueError):
            stage(root,"luna/development.py",sha,"def broken(:\n")


def test_workshop_api_rejects_non_allowlisted_entrypoint():
    from fastapi.testclient import TestClient
    from app import app
    response=TestClient(app).post("/development/workshop/stage",json={
        "path":"app.py","base_sha256":"0"*64,"replacement":"VALUE=2"})
    assert response.status_code==400
