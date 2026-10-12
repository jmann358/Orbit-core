"""Local SQLite backup/verification, never automatic remote sync or restore.

Backups contain private conversation data. Keep files on the trusted host,
restrict permissions and NEVER check them into source control.
"""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import hashlib
import os
import sqlite3
from luna import core


def _readonly(path):
    if not isinstance(path, (str, Path)):
        raise ValueError("Invalid database path")
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError("SQLite file not present")
    uri = "file:" + quote(str(path), safe="/") + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def verify(path):
    """Open without creating or modifying source database."""
    with _readonly(path) as db:
        status = db.execute("PRAGMA integrity_check").fetchone()[0]
        tables = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    return {
        "integrity_ok": status == "ok", "tables": tables,
        "read_only_check": True,
    }


def backup(source, destination):
    """Consistent snapshot into a *new* user-chosen local .db path.

    Uses SQLite's online backup API for WAL safety. Never overwrites an
    existing file, changes the source, or creates an accessible server.
    """
    if not isinstance(destination, (str, Path)):
        raise ValueError("Invalid destination")
    target = Path(destination)
    if target.suffix != ".db":
        raise ValueError("Backup must be a .db file to remain gitignored")
    if target.is_symlink() or target.exists():
        raise FileExistsError("Backup target already exists")
    if not verify(source)["integrity_ok"]:
        raise ValueError("Source database integrity check failed")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Exclusive creation prevents overwrites and symlink races.
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with _readonly(source) as source_db:
            with sqlite3.connect(target) as destination_db:
                source_db.backup(destination_db)
        if not verify(target)["integrity_ok"]:
            raise ValueError("Copied database integrity check failed")
        os.chmod(target, 0o600)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return {
            "verified": True, "sha256": digest,
            "bytes": target.stat().st_size,
            "mode": "offline_local_sqlite_snapshot",
            "source_unchanged": True, "restore_performed": False,
        }
    except Exception:
        # This function created the destination exclusively. Remove only
        # its incomplete output; never touch the source or prior backups.
        target.unlink(missing_ok=True)
        raise


def backup_default():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return backup(core.DB_PATH, Path("backups") / ("luna-" + stamp + ".db"))
