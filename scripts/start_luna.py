#!/usr/bin/env python3
"""Start the existing Luna web product safely, without updates or side effects.

Run: python scripts/start_luna.py
Check: python scripts/start_luna.py --check
Never binds the unauthenticated dashboard to a network interface.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("fastapi", "uvicorn", "httpx")
HOST = "127.0.0.1"
PORT = 8000


def readiness():
    missing = [name for name in REQUIRED if importlib.util.find_spec(name) is None]
    return {
        "python_supported": sys.version_info >= (3, 11),
        "missing_dependencies": missing,
        "dashboard_url": f"http://{HOST}:{PORT}",
        "model_url_configured": bool(os.getenv("LUNA_MODEL_URL")),
        "model_name_configured": bool(os.getenv("LUNA_MODEL_NAME")),
        "model_key_configured": bool(os.getenv("LUNA_API_KEY")),
        "remote_phone_access_enabled": False,
    }


def server_command():
    return [
        sys.executable, "-m", "uvicorn", "app:app",
        "--host", HOST, "--port", str(PORT),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Launch Luna on this computer only")
    parser.add_argument("--check", action="store_true", help="Print local readiness; do not start server")
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    status = readiness()
    if args.check:
        print(json.dumps(status, indent=2))
        return 0 if status["python_supported"] and not status["missing_dependencies"] else 1
    if not status["python_supported"]:
        print("Luna requires Python 3.11 or newer.", file=sys.stderr)
        return 1
    if status["missing_dependencies"]:
        print(
            "Missing Python packages: " + ", ".join(status["missing_dependencies"]) +
            "\nInstall with: python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    print("Luna is starting locally at " + status["dashboard_url"], flush=True)
    print("Open that address in a browser on THIS computer.", flush=True)
    print("Chats and other local data persist in the configured SQLite database.", flush=True)
    print("Do not expose this unauthenticated server to your network or the internet.", flush=True)
    if not (status["model_url_configured"] and status["model_name_configured"]):
        print(
            "AI chat model not fully configured: dashboard works, but model-backed replies may be unavailable.",
            flush=True,
        )
    print("Press Ctrl+C to stop Luna. No git pull, software install, or cloud request is performed by this launcher.", flush=True)
    try:
        return subprocess.call(server_command(), cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
