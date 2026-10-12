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
    # abspath normalizes the caller-provided path WITHOUT following symlinks.
    # Calling Path.resolve() here would let a raced root symlink silently
    # retarget our later O_NOFOLLOW open to an external directory.
    project_root = Path(os.path.abspath(os.fspath(project_root)))
    if project_root.is_symlink():
        raise ValueError("Refusing a symlinked project root")
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
    # Retain an actionable diagnostic for an already-linked destination.
    # The root-relative O_NOFOLLOW open below also rejects race replacements.
    if backup_dir.is_symlink():
        raise ValueError("Refusing a symlinked memory backup directory")

    # Anchor *both* the root and backup directory. Opening only backups with
    # O_NOFOLLOW does not protect against replacing its parent directory.
    # Creation below uses only dir_fd-relative operations until completion.
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "luna-before-self-build-" + stamp + "-" + secrets.token_hex(5) + ".sqlite"
    destination = backup_dir / name

    root_fd = None
    directory_fd = None
    file_fd = None
    created = False
    try:
        root_fd = os.open(project_root, directory_flags)
        original_root = os.fstat(root_fd)
        if not stat.S_ISDIR(original_root.st_mode):
            raise ValueError("Memory project root is not a directory")
        try:
            os.mkdir("backups", mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            pass
        directory_fd = os.open("backups", directory_flags, dir_fd=root_fd)
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

        # Reject replacement of *either* the project root or its backups
        # child. The checks cannot redirect a write, since the data was sent
        # exclusively through the pinned directory-relative file handle.
        current_root = os.stat(project_root, follow_symlinks=False)
        current_dir = os.stat("backups", dir_fd=root_fd, follow_symlinks=False)
        if (not stat.S_ISDIR(current_root.st_mode)
                or (current_root.st_dev, current_root.st_ino)
                != (original_root.st_dev, original_root.st_ino)
                or not stat.S_ISDIR(current_dir.st_mode)
                or (current_dir.st_dev, current_dir.st_ino)
                != (original_dir.st_dev, original_dir.st_ino)):
            raise ValueError("Memory backup path changed during copy")
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
        if root_fd is not None:
            os.close(root_fd)
