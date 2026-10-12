#!/usr/bin/env python3
"""Start Luna's local chat app and independent agent worker together.

This is the local preview launcher only. It never binds publicly, buys a
service, merges code, activates cloud access, or installs dependencies.
A paid or cloud development model is never enabled by the launcher.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST = "127.0.0.1"
PORT = 8000


def check_readiness():
    from luna.developer_model import configuration
    missing = [
        package for package in ("fastapi", "uvicorn", "httpx")
        if importlib.util.find_spec(package) is None
    ]
    return {
        "python_supported": sys.version_info >= (3, 11),
        "missing_dependencies": missing,
        "dashboard_url": "http://" + HOST + ":" + str(PORT),
        "studio_url": "http://" + HOST + ":" + str(PORT) + "/agent/studio",
        "developer_model_configured_unverified": configuration()["ready"],
        "cloud_deployed": False,
        "remote_access": False,
    }


def commands():
    return [
        sys.executable, "-m", "uvicorn", "app:app",
        "--host", HOST, "--port", str(PORT),
    ], [sys.executable, str(ROOT / "scripts" / "cloud_worker.py")]


def terminate(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=8)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Luna and her background worker on this computer only"
    )
    parser.add_argument("--check", action="store_true",
                        help="Read-only configuration check, start nothing")
    parser.add_argument("--auto-drafts", action="store_true",
                        help="Opt in to one curated development mission daily")
    args = parser.parse_args(argv)
    ready = check_readiness()
    if args.check:
        import json
        print(json.dumps(ready, indent=2))
        return 0 if ready["python_supported"] and not ready["missing_dependencies"] else 1
    if not ready["python_supported"] or ready["missing_dependencies"]:
        print("Luna requires Python 3.11+ and installed requirements.txt dependencies.",
              file=sys.stderr)
        return 1
    if os.environ.get("LUNA_CLOUD_MODE") == "1":
        print("This launcher is localhost-only, not a cloud deployment.", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["LUNA_WORKER_ENABLED"] = "1"
    if args.auto_drafts:
        if not ready["developer_model_configured_unverified"]:
            print("To auto-draft, first enable and configure a trusted development model.",
                  file=sys.stderr)
            return 1
        env["LUNA_AGENT_AUTO_ENABLED"] = "1"
    # Explicit environment opt-ins remain valid. No flags implicitly enable
    # paid calls or the development model.
    web_command, worker_command = commands()
    print("Luna chat: " + ready["dashboard_url"], flush=True)
    print("Luna Agent Studio: " + ready["studio_url"], flush=True)
    print("Background worker enabled. Ctrl+C stops both processes.", flush=True)
    children = []
    try:
        children.append(subprocess.Popen(web_command, cwd=ROOT, env=env))
        children.append(subprocess.Popen(worker_command, cwd=ROOT, env=env))
        while True:
            for child in children:
                status = child.poll()
                if status is not None:
                    print("A Luna process exited; shutting down the other process.",
                          file=sys.stderr, flush=True)
                    return status if status != 0 else 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 130
    finally:
        for child in reversed(children):
            terminate(child)


if __name__ == "__main__":
    raise SystemExit(main())
