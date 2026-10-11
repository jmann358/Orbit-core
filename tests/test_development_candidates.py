import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from luna import core,development_candidates

def _project(folder):
    root=Path(folder)/"project"
    (root/"luna").mkdir(parents=True)
    target=root/"luna"/"development.py"
    target.write_text("VALUE = 1\n")
    return root,target

def test_candidate_queue_allows_only_one_revised_retry():
    with tempfile.TemporaryDirectory() as folder:
        root,target=_project(folder)
        base=hashlib.sha256(target.read_bytes()).hexdigest()
        with patch.object(core,"DB_PATH",Path(folder)/"candidates.db"):
            first=development_candidates.create(
                root,"luna/development.py",base,"VALUE = 2\n")
            assert first["created"] is True
            assert first["attempt_number"]==1
            duplicate=development_candidates.create(
                root,"luna/development.py",base,"VALUE = 2\n")
            assert duplicate["created"] is False

            claimed=development_candidates.claim_next()
            assert claimed["id"]==first["id"]
            assert claimed["attempt_number"]==1
            assert development_candidates.finish(
                first["id"],"retry_allowed",{"tests_executed":True,"returncode":1})

            second=development_candidates.create(
                root,"luna/development.py",base,"VALUE = 3\n",
                parent_id=first["id"])
            assert second["attempt_number"]==2
            with pytest.raises(ValueError):
                development_candidates.create(
                    root,"luna/development.py",base,"VALUE = 4\n",
                    parent_id=first["id"])

def test_candidate_listing_never_returns_replacement_source():
    with tempfile.TemporaryDirectory() as folder:
        root,target=_project(folder)
        base=hashlib.sha256(target.read_bytes()).hexdigest()
        with patch.object(core,"DB_PATH",Path(folder)/"candidates.db"):
            development_candidates.create(
                root,"luna/development.py",base,"VALUE = 2\n")
            item=development_candidates.list_candidates()[0]
            assert "replacement" not in item
            assert item["state"]=="queued"
