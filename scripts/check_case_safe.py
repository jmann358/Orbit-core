#!/usr/bin/env python3
"""Reject case-colliding Git paths before they break a Mac checkout."""
import subprocess
import sys


def collisions(paths):
    grouped = {}
    for path in paths:
        grouped.setdefault(path.casefold(), []).append(path)
    return [values for values in grouped.values() if len(set(values)) > 1]


def main():
    result = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    )
    paths = [p.decode("utf-8") for p in result.stdout.split(b"\0") if p]
    problems = collisions(paths)
    if problems:
        for names in problems:
            print("Case-insensitive path collision: " + " | ".join(names),
                  file=sys.stderr)
        return 1
    print("Git paths are case-safe for macOS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
