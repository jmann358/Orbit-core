import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from luna import core
from luna.development import inspect_source
from luna.patches import review_patch
from luna.permissions import policy, request_grant, grant, revoke, check, consume
from luna.technical_memory import record, list_decisions


def test_inspector_reports_syntax_errors_without_modifying_source():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/"app.py").write_text("def broken(:\n")
        before=(root/"app.py").read_bytes()
        report=inspect_source(root)
        assert any(f["path"]=="app.py" and f["severity"]=="high" for f in report["findings"])
        assert (root/"app.py").read_bytes()==before
        assert not report["tests_run"] and not report["files_changed"]


def test_patch_preview_is_revision_locked_and_never_writes():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/"luna").mkdir()
        target=root/"luna"/"development.py"
        target.write_text("x=1\n")
        sha=hashlib.sha256(target.read_bytes()).hexdigest()
        report=review_patch(root,"luna/development.py",sha,"x=2\n")
        assert report["changed"] and report["syntax_valid"]
        assert not report["applied"] and not report["tests_run"]
        assert target.read_text()=="x=1\n"
        with pytest.raises(ValueError):
            review_patch(root,"luna/development.py","0"*64,"x=3\n")
        with pytest.raises(ValueError):
            review_patch(root,"app.py",sha,"x=3\n")
        with pytest.raises(ValueError):
            review_patch(root,"luna/development.py",sha,"def broken(:\n")


def test_permission_grants_expire_and_revoke():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"perm.db"):
            assert not check("apply_code")
            assert not check("prepare_patch")
            assert not request_grant("prepare_patch")["granted"]
            with pytest.raises(ValueError):
                grant("apply_code",30,"owner")
            with pytest.raises(ValueError):
                grant("run_tests",30,"luna")
            gid=grant("prepare_patch",30,"owner")
            assert check("prepare_patch")
            assert consume("prepare_patch")
            assert revoke(gid)
            assert not check("prepare_patch")
            assert not consume("apply_code")
            assert not policy()["automatic_expansion"]


def test_technical_decisions_are_separate_and_deduplicated():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"memory.db"):
            first=record("Mobile home","Mac mini primary; selected cloud tasks")
            assert first["created"]
            assert not record("Mobile home","Mac mini primary; selected cloud tasks")["created"]
            assert list_decisions()[0]["source"]=="owner"
            with pytest.raises(ValueError):
                record("Secret","Don't store personal information","unreviewed_model")
