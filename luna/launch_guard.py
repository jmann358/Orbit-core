"""Fail-closed, local-only safety checks before enabling self-building.

The owner's SQLite database is NEVER migrated, modified or sent to GitHub.
A consistent SQLite snapshot is created locally before the agent starts.
No cloud, paid, provider, installer or network operations occur here.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
import secrets
import sqlite3
from contextlib import closing
from urllib.parse import quote


def snapshot_existing_memory(db_path, *, project_root):
    """Create a private, consistent backup when an existing DB is present.

    Return None when there is no existing database. The caller must refuse to
    start unattended self-development if an existing DB cannot be backed up.
    Source is opened read-only; the SQLite backup API takes a consistent copy.
    """
    project_root = Path(project_root).resolve()
    requested = Path(db_path)
    if not requested.is_absolute():
        requested = project_root / requested
    if requested.is_symlink():
        raise ValueError("Refusing to follow a memory database symlink")
    if not requested.exists():
        return None
    if not requested.is_file():
        raise ValueError("Luna's memory path is not a regular database file")
    source = requested.resolve(strict=True)
    if source == Path(project_root / "backups"):
        raise ValueError("Invalid memory database location")

    backup_dir = project_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "luna-before-self-build-" + stamp + "-" + secrets.token_hex(5) + ".sqlite"
    destination = backup_dir / name

    # The backup can contain private conversations, so it must never be
    # created with world-readable permissions.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        uri = "file:" + quote(str(source), safe="/") + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as original:
            with closing(sqlite3.connect(destination, timeout=5)) as copy:
                original.backup(copy, pages=128, sleep=0.1)
                result = copy.execute("PRAGMA integrity_check").fetchone()
                if result != ("ok",):
                    raise ValueError("SQLite backup integrity check failed")
        os.chmod(destination, 0o600)
        return destination
    except (OSError, sqlite3.Error, ValueError) as exc:
        destination.unlink(missing_ok=True)
        raise ValueError("Local memory backup failed; self-building was not started") from None
