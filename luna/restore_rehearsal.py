"""Disposable, read-only restore rehearsal for Luna's local SQLite snapshots.

Never restores over the live database. The caller chooses an existing backup;
this tool copies it into a temporary directory, checks integrity and tables,
and destroys the rehearsal copy before returning.
"""
from pathlib import Path
import shutil
import sqlite3
import tempfile

from luna.database_backup import verify


def rehearse_restore(snapshot):
    path = Path(snapshot)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Restore rehearsal requires a regular snapshot file")
    original = verify(path)
    if not original["integrity_ok"]:
        raise ValueError("Backup integrity check failed")
    with tempfile.TemporaryDirectory(prefix="luna-restore-check-") as folder:
        temporary = Path(folder) / "rehearsal.db"
        # SQLite backup API produces a consistent snapshot even if the
        # selected backup is open in another process.
        with sqlite3.connect(
            "file:" + str(path.resolve()) + "?mode=ro", uri=True
        ) as source:
            with sqlite3.connect(temporary) as target:
                source.backup(target)
        restored = verify(temporary)
        if not restored["integrity_ok"] or restored["tables"] != original["tables"]:
            raise ValueError("Restore rehearsal verification failed")
    return {
        "rehearsed": True,
        "integrity_ok": True,
        "tables": original["tables"],
        "live_database_replaced": False,
        "temporary_copy_deleted": True,
    }
