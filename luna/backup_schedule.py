"""Safe, bounded on-host backup cadence for Luna's always-running Mac service.

Only the trusted local SQLite source is copied. No remote writes, no uploads,
no deletion of previous snapshots, and no owner credentials are touched.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import time

from luna.launch_guard import snapshot_existing_memory

DAY_SECONDS = 86400
PREFIX = "luna-before-self-build-"


def backup_due(root, *, now=None):
    """Fail closed if the backups directory cannot safely be inspected."""
    root = Path(root)
    directory = root / "backups"
    if directory.is_symlink():
        raise ValueError("Refusing a symlinked memory backup directory")
    if not directory.exists():
        return True
    if not directory.is_dir():
        raise ValueError("Memory backup destination is not a directory")
    now = time.time() if now is None else now
    try:
        for entry in directory.iterdir():
            if (entry.name.startswith(PREFIX)
                    and entry.suffix == ".sqlite"
                    and not entry.is_symlink() and entry.is_file()):
                age = now - entry.stat().st_mtime
                if 0 <= age < DAY_SECONDS:
                    return False
    except OSError:
        raise ValueError("Cannot verify private local backups") from None
    return True


def maybe_backup(db_path, *, root):
    """Snapshot at most once per day under normal single-worker operation."""
    if not backup_due(root):
        return {"created": False, "reason": "recent_local_snapshot"}
    target = Path(db_path)
    if not target.is_absolute():
        target = Path(root) / target
    if not target.exists():
        return {"created": False, "reason": "new_database"}
    snapshot = snapshot_existing_memory(db_path, project_root=root)
    return {"created": bool(snapshot), "reason": "backed_up" if snapshot else
            "new_database"}
