import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from luna import core,development_candidates,development_worker

def _project(folder):
    root=Path(folder)/"project"
    (root/"luna").mkdir(parents=True)
    target=root/"luna"/"development.py"
    target.write_text("VALUE = 1\n")
    return root,target

def test_worker_records_pass_without_live_write(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        root,target=_project(folder)
        base=hashlib.sha256(target.read_bytes()).hexdigest()
        original=target.read_text()
        with patch.object(core,"DB_PATH",Path(folder)/"worker.db"):
            created=development_candidates.create(
                root,"luna/development.py",base,"VALUE = 2\n")
            monkeypatch.setattr(
                development_worker,"evaluate_candidate",
                lambda *a,**k:{
                    "state":SimpleNamespace(status="ready_for_review"),
                    "runner":{"tests_executed":True,"returncode":0},
                })
            result=development_worker.run_one(root)
            assert result["candidate_id"]==created["id"]
            assert result["state"]=="passed"
            assert result["repair_status"]=="ready_for_review"
            assert result["live_files_changed"] is False
            assert target.read_text()==original
            saved=development_candidates.list_candidates()[0]
            assert saved["state"]=="passed"

def test_worker_maps_failed_first_attempt_to_retry_allowed(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        root,target=_project(folder)
        base=hashlib.sha256(target.read_bytes()).hexdigest()
        with patch.object(core,"DB_PATH",Path(folder)/"worker.db"):
            development_candidates.create(
                root,"luna/development.py",base,"VALUE = 2\n")
            monkeypatch.setattr(
                development_worker,"evaluate_candidate",
                lambda *a,**k:{
                    "state":SimpleNamespace(status="retry_allowed"),
                    "runner":{"tests_executed":True,"returncode":1},
                })
            result=development_worker.run_one(root)
            assert result["state"]=="retry_allowed"
            assert development_candidates.list_candidates()[0]["state"]=="retry_allowed"
