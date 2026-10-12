"""Fail-closed, local-only SQLite memory snapshot for unattended startup.

Never imports generated code, modifies the original database, writes to a
model, exposes a network endpoint or chooses a remote backup destination.
A verified directory and file descriptor stay open throughout the copy.
"""
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import sqlite3
import stat
from urllib.parse import quote


def snapshot_existing_memory(db_path, *, project_root):
    """Create a consistent private SQLite snapshot without reopening its path.

    Read the source in SQLite mode=ro and back up to an in-memory SQLite
    database first, then serialize and write directly through an O_NOFOLLOW
    O_EXCL file descriptor. The directory fd persists until the write and
    final directory identity verification finish. If the directory is swapped,
    remove our file *through the original directory fd* and fail closed.

    Return None if no source database existed. An error leaves the original
    database untouched and blocks the unattended launch.
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

    backup_dir = project_root / "backups"
    if backup_dir.is_symlink():
        raise ValueError("Refusing a symlinked memory backup directory")
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if backup_dir.is_symlink():
        raise ValueError("Refusing a symlinked memory backup directory")

    # On supported Unix/macOS targets these flags reject symlinks even when
    # a local process races the initial path check.
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "luna-before-self-build-" + stamp + "-" + secrets.token_hex(5) + ".sqlite"
    destination = backup_dir / name

    directory_fd = None
    file_fd = None
    created = False
    try:
        directory_fd = os.open(backup_dir, directory_flags)
        original_dir = os.fstat(directory_fd)
        if not stat.S_ISDIR(original_dir.st_mode):
            raise ValueError("Memory backup location is not a directory")
        file_fd = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600, dir_fd=directory_fd,
        )
        created = True

        # No operation after opening the directory needs to follow or reopen
        # the destination path. This prevents a directory swap from redirecting
        # the contents to an attacker-controlled location.
        uri = "file:" + quote(str(source), safe="/") + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as original:
            with closing(sqlite3.connect(":memory:", timeout=5)) as copy:
                original.backup(copy, pages=128, sleep=0.1)
                if copy.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("SQLite backup integrity check failed")
                if not hasattr(copy, "serialize"):
                    raise ValueError("SQLite serialization unavailable on this Python")
                serialized = copy.serialize()
        if not serialized:
            raise ValueError("SQLite backup serialization was empty")
        view = memoryview(serialized)
        offset = 0
        while offset < len(view):
            written = os.write(file_fd, view[offset:])
            if written < 1:
                raise OSError("SQLite backup write was incomplete")
            offset += written
        os.fchmod(file_fd, 0o600)
        os.fsync(file_fd)

        # The path must still designate the *same* directory descriptor. A
        # replacement symlink or a different ordinary directory both fail.
        current_dir = os.stat(backup_dir, follow_symlinks=False)
        if (not stat.S_ISDIR(current_dir.st_mode)
                or (current_dir.st_dev, current_dir.st_ino)
                != (original_dir.st_dev, original_dir.st_ino)):
            raise ValueError("Memory backup directory changed during copy")
        return destination
    except (OSError, sqlite3.Error, ValueError, AttributeError):
        if created and directory_fd is not None:
            try:
                os.unlink(name, dir_fd=directory_fd)
            except OSError:
                pass
        raise ValueError("Local memory backup failed; self-building was not started") from None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
