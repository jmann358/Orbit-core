"""Declarative fail-closed isolation profile for future Luna test execution.

This module describes requirements only; it never launches a process.
"""

PROFILE={
    "network":"deny",
    "host_filesystem":"read_only",
    "workspace":"disposable",
    "secrets":"unavailable",
    "time_limit_seconds":30,
    "memory_limit_mb":256,
    "max_retries":2,
}

def status():
    return {
        "profile":dict(PROFILE),
        "execution_enabled":False,
        "draft_execution_enabled":False,
        "shell_enabled":False,
        "dependency_install_enabled":False,
        "requires_verified_runner":True,
        "requires_owner_approval_to_enable":True,
        "fail_closed":True,
    }
