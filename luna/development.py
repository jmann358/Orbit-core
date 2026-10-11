"""Constrained development task registry and static draft checks.

Remote task descriptions are data, never instructions to execute.
"""
import ast
import re

ALLOWED_TASK_IDS = frozenset({"DEV-001", "DEV-002", "DEV-003"})
ALLOWED_EXECUTIONS = {"DEV-001": "read_only", "DEV-002": "planning_only", "DEV-003": "planning_only"}
MAX_TASKS = 40

def normalize_tasks(payload):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported shared task schema")
    entries = payload.get("tasks")
    if not isinstance(entries, list) or len(entries) > MAX_TASKS:
        raise ValueError("Invalid task list")
    result = []
    seen = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        task_id = item.get("id")
        if not isinstance(task_id, str) or not re.fullmatch(r"DEV-[0-9]{3}", task_id):
            continue
        if task_id in seen:
            raise ValueError("Duplicate task ID")
        seen.add(task_id)
        result.append({
            "id": task_id,
            "title": str(item.get("title", ""))[:160],
            "status": str(item.get("status", ""))[:40],
            "execution": str(item.get("execution", ""))[:40],
            "instructions": str(item.get("instructions", ""))[:1200],
            "eligible": task_id in ALLOWED_TASK_IDS and
                        item.get("execution") == ALLOWED_EXECUTIONS.get(task_id)
        })
    return result

def static_draft_report(content):
    """Inspect text without executing it, applying it, or trusting its claims."""
    if not isinstance(content, str):
        raise ValueError("Draft must be text")
    if len(content) > 100_000:
        raise ValueError("Draft exceeds static review limit")
    fences = re.findall(r"```(?:python|py)\s*\n(.*?)\n```", content, flags=re.I | re.S)
    checks = []
    for index, snippet in enumerate(fences[:12], start=1):
        try:
            ast.parse(snippet)
            checks.append({"block": index, "syntax": "valid"})
        except SyntaxError as exc:
            checks.append({"block": index, "syntax": "invalid",
                           "detail": str(exc)[:200]})
    return {
        "python_blocks_found": len(fences),
        "blocks_checked": len(checks),
        "checks": checks,
        "all_checked_blocks_parse": bool(checks) and all(x["syntax"] == "valid" for x in checks),
        "note": "Syntax-only screening. This does not prove correctness, safety, or applicability.",
        "executed": False,
        "applied": False
    }

def planning_report(task_id):
    """Produce an actionable checklist; does not call a model or run remote text."""
    if task_id == "DEV-002":
        return ("Draft-validation design: require a machine-readable file target and "
                "base revision; restrict paths to an explicit allowlist; parse Python "
                "candidate source with AST; show a diff; require regression tests in "
                "a separately secured runner before human-reviewed application.")
    if task_id == "DEV-003":
        return ("Scheduler design: persist enable state and last-run timestamp; "
                "single worker with a lock; fixed allowlisted read-only jobs; "
                "minimum interval and timeouts; activity journal; pause/stop control; "
                "no model-generated shell commands or automatic code deployment.")
    raise ValueError("No local planning template for this task")
