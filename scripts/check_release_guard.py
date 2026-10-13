#!/usr/bin/env python3
"""Offline, read-only audit of the pinned GitHub CI workflow launch guard.

This script NEVER trusts or updates a workflow and NEVER starts Luna, changes
Git, reads private SQLite, connects to GitHub or requests credentials.
A successful GitHub Actions run alone does not remove a pinned-workflow veto.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PIN_PATTERN = re.compile(r'(?m)^TRUSTED_WORKFLOW_BLOB="([0-9a-f]{40})"$')


def git_blob_sha(contents):
    """Hash raw Git blob bytes (repository currently uses SHA-1 Git objects)."""
    if not isinstance(contents, bytes):
        raise TypeError("Git blob contents must be bytes")
    header = f"blob {len(contents)}\0".encode("ascii")
    return hashlib.sha1(header + contents).hexdigest()


def check(guard_path, workflow_path):
    """Report trusted/pin mismatch, never alter a protection or grant trust."""
    source = Path(guard_path).read_text(encoding="utf-8")
    pins = PIN_PATTERN.findall(source)
    if len(pins) != 1:
        return {
            "status": "blocked", "reason": "missing_or_ambiguous_pin",
            "trusted_workflow": False,
        }
    workflow = Path(workflow_path).read_bytes()
    actual = git_blob_sha(workflow)
    pin = pins[0]
    return {
        "status": "trusted" if pin == actual else "blocked",
        "reason": "pin_matches" if pin == actual else "workflow_pin_mismatch",
        "trusted_workflow": pin == actual,
        "pinned_git_blob": pin,
        "current_workflow_git_blob": actual,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only pin-vs-workflow audit; does not certify CI or deployment"
    )
    parser.add_argument("--guard", type=Path,
                        default=ROOT / "scripts" / "verify_and_launch.sh")
    parser.add_argument("--workflow", type=Path,
                        default=ROOT / ".github" / "workflows" / "orbit-checks.yml")
    args = parser.parse_args(argv)
    try:
        result = check(args.guard, args.workflow)
    except (OSError, UnicodeError, ValueError, TypeError):
        result = {"status": "blocked", "reason": "inspection_failed",
                  "trusted_workflow": False}
    print(json.dumps({**result, "read_only": True,
                      "release_approved": False}, sort_keys=True))
    return 0 if result["trusted_workflow"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
