"""Safe local backup and recovery planning for Luna's SQLite state.

Creates consistent SQLite snapshots using SQLite's backup API. Restore is planning-only:
this module never overwrites the live database and never deletes old backups.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from luna import core

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR=ROOT/"backups"
PREFIX="luna_local-"

def _now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def _safe_dir(destination_dir=None):
    directory=Path(destination_dir) if destination_dir is not None else DEFAULT_BACKUP_DIR
    directory=directory.resolve()
    directory.mkdir(parents=True,exist_ok=True)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Unsafe backup directory")
    return directory

def validate(path):
    path=Path(path).resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Unsafe backup file")
    try:
        with sqlite3.connect(path) as db:
            row=db.execute("PRAGMA quick_check").fetchone()
            tables=db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        return {"valid":False,"integrity":"database_error","tables":0,"bytes":path.stat().st_size}
    integrity=row[0] if row else "unknown"
    return {
        "valid":integrity=="ok",
        "integrity":integrity,
        "tables":tables,
        "bytes":path.stat().st_size,
    }

def create(destination_dir=None):
    """Create and validate one consistent snapshot. Never mutates the live DB."""
    directory=_safe_dir(destination_dir)
    stamp=_now_stamp()
    target=directory/(PREFIX+stamp+".db")
    suffix=1
    while target.exists():
        target=directory/(PREFIX+stamp+"-"+str(suffix)+".db")
        suffix+=1

    source=core.connect()
    try:
        destination=sqlite3.connect(target)
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
    finally:
        source.close()

    result=validate(target)
    if not result["valid"]:
        try:
            target.unlink()
        except OSError:
            pass
        raise RuntimeError("Backup failed integrity validation")

    manifest={
        "schema_version":1,
        "filename":target.name,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "bytes":result["bytes"],
        "tables":result["tables"],
        "integrity":result["integrity"],
        "live_database_modified":False,
        "restore_performed":False,
    }
    manifest_path=target.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return {**manifest,"path":str(target),"manifest":str(manifest_path)}

def list_backups(destination_dir=None,limit=30):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("Invalid backup limit")
    directory=_safe_dir(destination_dir)
    items=[]
    for path in sorted(directory.glob(PREFIX+"*.db"),key=lambda p:p.stat().st_mtime,reverse=True)[:limit]:
        if path.is_symlink() or not path.is_file():
            continue
        items.append({
            "filename":path.name,
            "bytes":path.stat().st_size,
            "modified_at":datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
        })
    return items

def restore_plan(filename,destination_dir=None):
    """Return a validated owner-run restore plan. Never restores automatically."""
    if not isinstance(filename,str) or "/" in filename or "\\" in filename:
        raise ValueError("Backup filename only")
    directory=_safe_dir(destination_dir)
    candidate=(directory/filename).resolve(strict=True)
    if candidate.parent!=directory or not candidate.name.startswith(PREFIX) or candidate.suffix!=".db":
        raise ValueError("Backup is outside the allowed backup set")
    check=validate(candidate)
    if not check["valid"]:
        raise ValueError("Backup failed integrity validation")
    return {
        "backup":candidate.name,
        "target":str(core.DB_PATH.resolve()),
        "integrity":check["integrity"],
        "requires_owner_action":True,
        "server_must_be_stopped":True,
        "create_pre_restore_backup_first":True,
        "restore_performed":False,
        "automatic_overwrite_allowed":False,
    }
