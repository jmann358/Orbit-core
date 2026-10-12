"""Mac-safe checkout and memory recovery acceptance tests."""
from pathlib import Path
import sqlite3
import tempfile

import pytest

from luna.restore_rehearsal import rehearse_restore

ROOT = Path(__file__).resolve().parents[1]


def test_tracked_paths_have_no_case_insensitive_collisions():
    # This is also enforced against *all* Git-tracked paths by CI's
    # repository case-collision guard.
    assert (ROOT / "README.md").exists()
    names = [item.name for item in ROOT.iterdir()]
    assert names.count("README.md") == 1
    assert "readme.md" not in names
    assert len(names) == len({name.casefold() for name in names})


def test_rehearsal_never_changes_snapshot_or_live_memory():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        live = root / "live.db"
        snapshot = root / "backup.db"
        with sqlite3.connect(live) as db:
            db.execute("CREATE TABLE memory (value TEXT NOT NULL)")
            db.execute("INSERT INTO memory VALUES ('private memory')")
        with sqlite3.connect(live) as source:
            with sqlite3.connect(snapshot) as target:
                source.backup(target)
        before = snapshot.read_bytes()
        result = rehearse_restore(snapshot)
        assert result == {
            "rehearsed": True,
            "integrity_ok": True,
            "tables": 1,
            "live_database_replaced": False,
            "temporary_copy_deleted": True,
        }
        assert snapshot.read_bytes() == before
        with sqlite3.connect(live) as db:
            assert db.execute("SELECT value FROM memory").fetchone()[0] == "private memory"


def test_rehearsal_rejects_corrupt_and_symlinked_snapshots():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        broken = root / "broken.db"
        broken.write_text("not SQLite")
        with pytest.raises((ValueError, sqlite3.DatabaseError)):
            rehearse_restore(broken)
        linked = root / "linked.db"
        linked.symlink_to(broken)
        with pytest.raises(ValueError, match="regular snapshot"):
            rehearse_restore(linked)
