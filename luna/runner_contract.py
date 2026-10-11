"""Structured contract for a future isolated Luna validation runner.

The contract is declarative only. It never starts containers or processes.
"""
from luna.patches import ALLOWED_PATHS
from luna.isolation_policy import PROFILE

FIXED_TEST_TARGETS={
    "luna/development.py":"tests/test_development.py",
    "luna/self_improvement.py":"tests/test_self_improvement.py",
}

def prepare(relative_path, checkpoint):
    if relative_path not in ALLOWED_PATHS:
        raise ValueError("Runner target is not authorized")
    if not isinstance(checkpoint,dict) or checkpoint.get("path")!=relative_path:
        raise ValueError("Checkpoint does not match target")
    if checkpoint.get("requires_verified_base") is not True:
        raise ValueError("Verified base checkpoint required")
    return {
        "target":relative_path,
        "test_target":FIXED_TEST_TARGETS[relative_path],
        "isolation_profile":dict(PROFILE),
        "request_kind":"fixed_regression_test",
        "arbitrary_command_allowed":False,
        "network_allowed":False,
        "secrets_available":False,
        "code_application_allowed":False,
        "merge_allowed":False,
        "execution_enabled":False,
        "requires_run_tests_grant":True,
    }
