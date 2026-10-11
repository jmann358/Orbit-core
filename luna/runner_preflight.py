"""Read-only prerequisites for a future isolated test runner.

Never executes proposed source, launches a subprocess, or changes host settings.
"""
import os
import shutil
from pathlib import Path


def inspect_runner():
    executable=shutil.which("bwrap")
    if executable:
        path=Path(executable)
        safe=path.is_file() and not path.is_symlink() and os.access(path,os.X_OK)
    else:
        safe=False
    return {
        "runner":"bubblewrap",
        "available":bool(safe),
        "isolated_tests_enabled":False,
        "draft_execution_enabled":False,
        "network_policy":"deny (required, not yet implemented)",
        "filesystem_policy":"read-only host, disposable writable workspace (required, not yet implemented)",
        "time_limit_seconds":30,
        "memory_limit_mb":256,
        "max_retries":2,
        "approval_required":True,
        "next_step":"Implement and verify fail-closed sandbox invocation before enabling test execution",
    }
