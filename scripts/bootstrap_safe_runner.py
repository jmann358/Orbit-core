#!/usr/bin/env python3
"""Read-only safe-runner prerequisite report.

This command does not install packages, execute draft code, or enable a sandbox.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from luna.runner_preflight import inspect_runner


def main():
    report = inspect_runner()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["available"]:
        print("Bubblewrap executable detected; isolated execution is NOT enabled.")
    else:
        print("Bubblewrap not detected or unsafe; isolated execution remains disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
