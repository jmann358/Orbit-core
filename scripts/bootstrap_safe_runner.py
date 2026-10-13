#!/usr/bin/env python3
"""Read-only report of existing Linux runner prerequisites.

This is not a runner installer, sandbox activation, container execution,
credential probe, or authorization to execute generated source.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luna.runner_preflight import inspect_runner


def main():
    report = inspect_runner()
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "No isolated candidate execution was enabled or attempted. "
        "Runner availability is only an unverified prerequisite."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
