"""Luna's opt-in independent agent worker.

The process keeps handling durable, allowlisted jobs without a browser tab.
Self-directed development is enabled only with LUNA_AGENT_AUTO_ENABLED=1,
LUNA_AGENT_MODEL_ENABLED=1 and a configured approved model. No deployment.
"""
import argparse
import asyncio
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luna.cloud_worker import process_one
from luna.developer_agent import maybe_queue_automatic, run_mission
from luna.developer_model import configuration


def db_path():
    from luna.core import DB_PATH
    return DB_PATH


def handlers():
    def heartbeat():
        return "alive"

    def health():
        # Fixed local check, not a shell command or model-generated code.
        files = ("app.py", "luna/core.py", "requirements.txt")
        if not all((ROOT / name).is_file() for name in files):
            raise RuntimeError("Required source missing")
        return "source files present"

    def develop(mission_id):
        if not mission_id.isdecimal() or len(mission_id) > 10:
            raise ValueError("Invalid mission identifier")
        result = asyncio.run(run_mission(db_path(), int(mission_id), root=ROOT))
        # Publishing a draft PR does not merge or deploy it. This separate
        # opt-in requires a repository-scoped GitHub token on the host.
        if os.environ.get("LUNA_GITHUB_PR_AUTO_ENABLED") == "1":
            from luna.self_build import publish_review_pr
            published = publish_review_pr(db_path(), int(mission_id), root=ROOT)
            return result + "; draft PR: " + published["url"]
        return result

    return {
        "heartbeat": heartbeat,
        "project_health": health,
        "development_draft": develop,
    }


_next_backup_check = 0.0
_backup_blocked = False


def _service_backup_tick():
    """Stop unattended work until a required recovery snapshot succeeds."""
    global _next_backup_check, _backup_blocked
    if os.environ.get("LUNA_SERVICE_MODE") != "1":
        return True
    now = time.monotonic()
    if now < _next_backup_check:
        return not _backup_blocked
    try:
        from luna.backup_schedule import maybe_backup
        result = maybe_backup(db_path(), root=ROOT)
    except (ValueError, OSError, sqlite3.Error):
        # Skip this tick without running tasks. Retry the backup immediately
        # on the next tick instead of taking down the supervised processes.
        _backup_blocked = True
        _next_backup_check = now
        print("Luna's private local backup failed; worker tick skipped.",
              file=sys.stderr, flush=True)
        return False
    _backup_blocked = False
    _next_backup_check = now + (
        60 if result.get("reason") == "new_database" else 3600
    )
    return True


def run_once():
    if not _service_backup_tick():
        return None
    maybe_queue_automatic(db_path())
    return process_one(db_path(), handlers())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Luna supervised agent worker")
    parser.add_argument("--once", action="store_true",
                        help="Run one eligible task then exit")
    parser.add_argument("--check", action="store_true",
                        help="Check readiness without queuing or calling any model")
    args = parser.parse_args(argv)
    if args.check:
        # This mode is truly read-only. It neither opens nor initializes SQLite.
        ready = configuration()
        print("Luna worker ready; no database changed and no tasks executed.")
        print("Developer model configured (unverified): " + str(ready["ready"]))
        print("Automatic drafts: " + str(os.environ.get("LUNA_AGENT_AUTO_ENABLED") == "1"))
        return 0
    if args.once:
        print(run_once())
        return 0
    if os.environ.get("LUNA_WORKER_ENABLED") != "1":
        parser.error("Set LUNA_WORKER_ENABLED=1 to run continuously")
    try:
        while True:
            result = run_once()
            if result is None:
                time.sleep(5)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
