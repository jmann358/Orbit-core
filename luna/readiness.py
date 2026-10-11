"""Local, read-only ORBIT readiness snapshot.

Reports capability prerequisites without exposing credentials or changing settings.
"""
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from luna import core
from luna.runner_preflight import inspect_runner
from luna.runner_config import approved_image
from luna.permissions import check
from luna.continuity import status as continuity_status
from luna.autopilot import status as autopilot_status
from luna.worker_heartbeat import status as worker_status

def _version(root):
    file=Path(root)/"VERSION"
    try:
        value=file.read_text(encoding="utf-8").strip()
    except OSError:
        return {"ok":False,"value":None,"reason":"version_file_unavailable"}
    return {"ok":bool(value),"value":value or None,"reason":None if value else "version_file_empty"}

def _database():
    path=core.DB_PATH
    result={"path_kind":"local_file","exists":path.exists(),"symlink":path.is_symlink(),
            "quick_check":"not_run","ok":False}
    if path.is_symlink():
        result["quick_check"]="blocked_symlink"
        return result
    try:
        with core.connect() as db:
            row=db.execute("PRAGMA quick_check").fetchone()
        result["quick_check"]=row[0] if row else "unknown"
        result["ok"]=result["quick_check"]=="ok"
    except (sqlite3.Error,OSError):
        result["quick_check"]="failed"
    return result

def _model():
    endpoint=os.environ.get("LUNA_MODEL_URL","").strip()
    model=os.environ.get("LUNA_MODEL_NAME","").strip()
    key_present=bool(os.environ.get("LUNA_API_KEY",""))
    if not endpoint or not model:
        return {"configured":False,"kind":"none","model_named":bool(model),
                "credential_present":key_present}
    parsed=urlparse(endpoint)
    local=parsed.scheme=="http" and parsed.hostname in ("localhost","127.0.0.1")
    cloud=parsed.scheme=="https"
    return {"configured":True,"kind":"local" if local else "cloud" if cloud else "blocked",
            "model_named":True,"credential_present":key_present if cloud else False}

def snapshot(root):
    root=Path(root).resolve(strict=True)
    runtime=inspect_runner()
    image=approved_image()
    version=_version(root)
    database=_database()
    model=_model()
    continuity=continuity_status()
    autopilot=autopilot_status()
    worker=worker_status()
    checks={
        "version_file":version["ok"],
        "database_integrity":database["ok"],
        "container_runtime":runtime["runtime_available"],
        "approved_test_image":bool(image),
        "temporary_test_grant":check("run_tests"),
        "model_configured":model["configured"],
        "background_worker":worker["alive"],
    }
    blockers=[name for name,ok in checks.items() if not ok]
    return {
        "ready_for_local_chat":checks["database_integrity"],
        "ready_for_isolated_tests":all(checks[name] for name in (
            "database_integrity","container_runtime","approved_test_image","temporary_test_grant")),
        "checks":checks,
        "blockers":blockers,
        "version":version,
        "database":database,
        "runner":{
            "runtime":runtime.get("runtime"),
            "runtime_available":runtime["runtime_available"],
            "approved_image_present":bool(image),
            "test_grant_active":checks["temporary_test_grant"],
        },
        "model":model,
        "continuity":{
            "pending":continuity["pending"],
            "approved":continuity["approved"],
        },
        "autopilot":{
            "enabled":autopilot["enabled"],
            "scope":autopilot["scope"],
        },
        "worker":worker,
        "secrets_returned":False,
        "changes_made":False,
    }
