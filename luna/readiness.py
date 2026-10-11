"""Local, read-only ORBIT readiness and diagnostics snapshot.

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
from luna.backup import list_backups, validate as validate_backup

TRUSTED_CLOUD_HOSTS=frozenset({
    "api.groq.com","api.openai.com","api.together.xyz",
    "openrouter.ai","generativelanguage.googleapis.com",
})

def _version(root):
    file=Path(root)/"VERSION"
    try:
        value=file.read_text(encoding="utf-8").strip()
    except OSError:
        return {"ok":False,"value":None,"reason":"version_file_unavailable"}
    return {"ok":bool(value),"value":value or None,
            "reason":None if value else "version_file_empty"}

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
        result["exists"]=path.exists()
    except (sqlite3.Error,OSError):
        result["quick_check"]="failed"
    return result

def _model():
    endpoint=os.environ.get("LUNA_MODEL_URL","").strip()
    model=os.environ.get("LUNA_MODEL_NAME","").strip()
    key_present=bool(os.environ.get("LUNA_API_KEY",""))
    if not endpoint or not model:
        return {
            "configured":False,"usable":False,"kind":"none",
            "model_named":bool(model),"credential_present":key_present,
            "trusted_endpoint":False,"reason":"model_or_endpoint_missing",
        }
    parsed=urlparse(endpoint)
    no_embedded_auth=not parsed.username and not parsed.password
    local=(parsed.scheme=="http" and parsed.hostname in ("localhost","127.0.0.1")
           and no_embedded_auth)
    cloud=(parsed.scheme=="https" and parsed.hostname in TRUSTED_CLOUD_HOSTS
           and parsed.port in (None,443) and no_embedded_auth)
    kind="local" if local else "cloud" if cloud else "blocked"
    usable=local or (cloud and key_present)
    reason=(None if usable else
            "cloud_credential_missing" if cloud and not key_present
            else "endpoint_not_trusted")
    return {
        "configured":True,
        "usable":usable,
        "kind":kind,
        "model_named":True,
        "credential_present":key_present if cloud else False,
        "trusted_endpoint":local or cloud,
        "reason":reason,
    }

def _backups():
    try:
        items=list_backups(limit=10)
    except (OSError,ValueError):
        return {"count":0,"latest":None,"latest_valid":False,"status":"unavailable"}
    latest=items[0] if items else None
    latest_valid=False
    if latest:
        try:
            from luna.backup import DEFAULT_BACKUP_DIR
            latest_valid=validate_backup(DEFAULT_BACKUP_DIR/latest["filename"])["valid"]
        except (OSError,ValueError):
            latest_valid=False
    return {
        "count":len(items),
        "latest":latest["filename"] if latest else None,
        "latest_valid":latest_valid,
        "status":"protected" if latest and latest_valid else "no_valid_backup",
    }

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
    backups=_backups()

    checks={
        "version_file":version["ok"],
        "database_integrity":database["ok"],
        "model_ready":model["usable"],
        "background_worker":worker["alive"],
        "container_runtime":runtime["runtime_available"],
        "approved_test_image":bool(image),
        "temporary_test_grant":check("run_tests"),
        "valid_local_backup":backups["latest_valid"],
    }

    required_for_dashboard=("version_file","database_integrity")
    required_for_model_chat=("version_file","database_integrity","model_ready")
    required_for_isolated_tests=(
        "database_integrity","container_runtime",
        "approved_test_image","temporary_test_grant")
    required_for_background_work=("database_integrity","background_worker")

    recommendations=[]
    if not checks["version_file"]:
        recommendations.append("Restore the VERSION file before relying on displayed build identity.")
    if not checks["database_integrity"]:
        recommendations.append("Stop write activity and inspect the local SQLite database before continuing.")
    if not checks["model_ready"]:
        if model["reason"]=="cloud_credential_missing":
            recommendations.append("A trusted cloud model is configured but its local credential is missing.")
        elif model["reason"]=="endpoint_not_trusted":
            recommendations.append("Use localhost or an allowlisted HTTPS model endpoint.")
        else:
            recommendations.append("Configure a local or approved cloud model to enable Luna chat responses.")
    if not checks["background_worker"]:
        recommendations.append("Restart Luna if background jobs should be processing.")
    if not checks["container_runtime"]:
        recommendations.append("Install or repair Podman/Docker before isolated development tests.")
    elif not checks["approved_test_image"]:
        recommendations.append("Run the safe-runner bootstrap to approve an immutable local test image.")
    elif not checks["temporary_test_grant"]:
        recommendations.append("The isolated runner is ready but its temporary test grant is inactive.")
    if not checks["valid_local_backup"]:
        recommendations.append("Create a validated local backup before risky maintenance or migrations.")

    blocking={
        "dashboard":[name for name in required_for_dashboard if not checks[name]],
        "model_chat":[name for name in required_for_model_chat if not checks[name]],
        "isolated_tests":[name for name in required_for_isolated_tests if not checks[name]],
        "background_work":[name for name in required_for_background_work if not checks[name]],
    }
    return {
        "ready_for_dashboard":not blocking["dashboard"],
        "ready_for_local_chat":not blocking["model_chat"],
        "ready_for_model_chat":not blocking["model_chat"],
        "ready_for_isolated_tests":not blocking["isolated_tests"],
        "ready_for_background_work":not blocking["background_work"],
        "checks":checks,
        "blocking":blocking,
        "blockers":sorted({item for items in blocking.values() for item in items}),
        "recommendations":recommendations,
        "version":version,
        "database":database,
        "runner":{
            "runtime":runtime.get("runtime"),
            "runtime_available":runtime["runtime_available"],
            "approved_image_present":bool(image),
            "test_grant_active":checks["temporary_test_grant"],
        },
        "model":model,
        "backups":backups,
        "continuity":{
            "pending":continuity["pending"],
            "approved":continuity["approved"],
            "revoked":continuity.get("revoked",0),
        },
        "autopilot":{
            "enabled":autopilot["enabled"],
            "scope":autopilot["scope"],
        },
        "worker":worker,
        "secrets_returned":False,
        "changes_made":False,
    }
