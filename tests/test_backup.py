import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from luna import backup,core

def test_backup_creates_consistent_valid_snapshot_and_restore_plan_only():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        db_path=root/"live.db"
        backup_dir=root/"backups"
        with patch.object(core,"DB_PATH",db_path):
            core.add_message("s","user","hello")
            result=backup.create(backup_dir)
            assert result["integrity"]=="ok"
            assert result["live_database_modified"] is False
            assert result["restore_performed"] is False
            assert Path(result["path"]).is_file()
            assert Path(result["manifest"]).is_file()

            core.add_message("s","user","after backup")
            with sqlite3.connect(result["path"]) as db:
                count=db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            assert count==1

            listed=backup.list_backups(backup_dir)
            assert listed[0]["filename"]==result["filename"]

            plan=backup.restore_plan(result["filename"],backup_dir)
            assert plan["requires_owner_action"] is True
            assert plan["server_must_be_stopped"] is True
            assert plan["create_pre_restore_backup_first"] is True
            assert plan["restore_performed"] is False
            assert plan["automatic_overwrite_allowed"] is False

def test_backup_validation_rejects_non_database():
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/"bad.db"
        path.write_text("not sqlite")
        result=backup.validate(path)
        assert result["valid"] is False
        assert result["integrity"]=="database_error"

def test_restore_plan_rejects_path_traversal():
    with tempfile.TemporaryDirectory() as folder:
        with pytest.raises(ValueError):
            backup.restore_plan("../live.db",Path(folder))
