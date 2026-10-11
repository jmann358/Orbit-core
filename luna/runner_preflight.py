"""Read-only report for the manually approved Linux candidate test runner.

Availability does not mean the local kernel permits user namespaces.
No program is executed by this inspection function.
"""
import os
import shutil
import sys
from pathlib import Path


def inspect_runner():
    executable = shutil.which("bwrap") if sys.platform == "linux" else None
    path = Path(executable) if executable else None
    safe = bool(
        path and path.is_file() and not path.is_symlink()
        and os.access(path, os.X_OK)
        and (path.resolve().is_relative_to(Path("/usr"))
             or path.resolve().is_relative_to(Path("/bin")))
    )
    return {
        "runner": "bubblewrap",
        "available": safe,
        "kernel_isolation_verified": False,
        "manual_candidate_tests_supported": safe,
        "isolated_tests_enabled": False,
        "automatic_candidate_execution_enabled": False,
        "draft_execution_enabled": False,
        "network_policy": "deny: unshare-all includes network namespace",
        "filesystem_policy": "allowlisted source snapshot read-only, private temporary filesystem",
        "time_limit_seconds": 30,
        "memory_limit_mb": 768,
        "max_output_bytes": 1048576,
        "max_retries": 0,
        "approval_required": True,
        "next_step": ("Use the owner-confirmed local CLI only after reviewing the fingerprint."
                      if safe else
                      "Optional bubblewrap installation and user namespace support are not verified."),
    }
