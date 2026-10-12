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
    # A symlinked directory could send private memories outside the protected
    # checkout, for example into a cloud-synced or shared folder.
    if backup_dir.is_symlink():
        raise ValueError("Refusing a symlinked memory backup directory")
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if backup_dir.is_symlink():
        raise ValueError("Refusing a symlinked memory backup directory")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "luna-before-self-build-" + stamp + "-" + secrets.token_hex(5) + ".sqlite"
    destination = backup_dir / name

    # Verify that the open directory itself is real, without following links.
    # Create the file relative to that directory descriptor, not via an
    # unverified path. O_EXCL prevents clobbering previous backups.
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    try:
        directory_fd = os.open(backup_dir, directory_flags)
        try:
            fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
                0o600, dir_fd=directory_fd,
            )
            os.close(fd)
        finally:
            os.close(directory_fd)
    except OSError:
        raise ValueError("Local memory backup directory is unsafe") from None
    if backup_dir.is_symlink():
        destination.unlink(missing_ok=True)
        raise ValueError("Refusing a symlinked memory backup directory")
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
