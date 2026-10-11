"""Read-only prerequisites for a future isolated test runner.

Never executes proposed source, launches a subprocess, or changes host settings.
"""
import os
import shutil
from pathlib import Path

RUNTIME_CANDIDATES=("podman","docker")

def _detect_runtime():
    for name in RUNTIME_CANDIDATES:
        executable=shutil.which(name)
        if not executable:
            continue
        path=Path(executable).resolve()
        if path.is_file() and not path.is_symlink() and os.access(path,os.X_OK):
            return {"name":name,"path":str(path)}
    return None

def inspect_runner():
    runtime=_detect_runtime()
    return {
        "runner":"container",
        "runtime":runtime["name"] if runtime else None,
        "runtime_path":runtime["path"] if runtime else None,
        "runtime_available":bool(runtime),
        "runtime_candidates":list(RUNTIME_CANDIDATES),
        "isolated_tests_enabled":False,
        "draft_execution_enabled":False,
        "network_policy":"deny plus pull-never required before execution",
        "filesystem_policy":"read-only host, disposable writable workspace required",
        "time_limit_seconds":30,
        "memory_limit_mb":256,
        "max_retries":2,
        "approval_required":True,
        "next_step":"Verify a pinned local image and temporary run-tests grant",
    }
