"""Cloud worker entry point. Does nothing unless explicitly started.

No scheduler is automatically enabled. Worker and web server must share a
persistent database volume. Only read-only heartbeat and health handlers run.
"""
import argparse
import os
from pathlib import Path
import time

from luna.cloud_worker import process_one, summary

ROOT = Path(__file__).resolve().parents[1]


def db_path():
    from luna.core import DB_PATH
    return DB_PATH


def handlers():
    def heartbeat():
        return "alive"

    def health():
        # This is a fixed local check, not a shell command or model call.
        files = ("app.py", "luna/core.py", "requirements.txt")
        if not all((ROOT / name).is_file() for name in files):
            raise RuntimeError("Required source missing")
        return "source files present"

    return {"heartbeat": heartbeat, "project_health": health}


def run_once():
    return process_one(db_path(), handlers())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Luna supervised cloud worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        print("Cloud worker available; no jobs executed or scheduled")
        return 0
    if args.once:
        print(run_once())
        return 0
    if os.environ.get("LUNA_WORKER_ENABLED") != "1":
        parser.error("Set LUNA_WORKER_ENABLED=1 explicitly to run continuously")
    while True:
        result = run_once()
        if result is None:
            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
