"""Machine-readable development relay records.

Relay records contain verification metadata only. They never carry source code,
credentials, model prompts, shell commands, or authority to apply changes.
"""
from datetime import datetime, timezone
import re

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_RESULTS = frozenset({"passed", "failed", "blocked"})
ALLOWED_GATES = frozenset({"tests", "syntax", "security", "compatibility"})


def build_report(*, commit_sha, result, checks, blocked_gates=()):
    if not isinstance(commit_sha, str) or not SHA_RE.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a full lowercase Git SHA")
    if result not in ALLOWED_RESULTS:
        raise ValueError("unsupported relay result")
    if not isinstance(checks, dict):
        raise TypeError("checks must be a mapping")
    clean_checks = {}
    for name, value in checks.items():
        if name not in ALLOWED_GATES or not isinstance(value, bool):
            raise ValueError("invalid relay check")
        clean_checks[name] = value
    gates = sorted(set(blocked_gates))
    if any(gate not in ALLOWED_GATES for gate in gates):
        raise ValueError("invalid blocked gate")
    if result == "passed" and gates:
        raise ValueError("passed report cannot contain blocked gates")
    return {
        "schema_version": 1,
        "commit_sha": commit_sha,
        "result": result,
        "checks": clean_checks,
        "blocked_gates": gates,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": "verification_only",
        "may_apply_code": False,
        "may_merge": False,
        "may_expand_permissions": False,
    }


def luna_view(report):
    """Return the minimal status Luna may consume."""
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("unsupported relay schema")
    return {
        "commit_sha": report["commit_sha"],
        "result": report["result"],
        "checks": dict(report.get("checks", {})),
        "blocked_gates": list(report.get("blocked_gates", [])),
        "authority": "verification_only",
    }
