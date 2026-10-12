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
import json
import socket
from urllib.request import urlopen
from urllib.error import URLError

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


def discover_ollama():
    """Probe a pre-existing local Ollama instance; never install/pull models."""
    try:
        with urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            if response.status != 200:
                return None
            payload = json.load(response)
        names = [
            item.get("name") for item in payload.get("models", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        # Explicitly prefer code-specialized models when already installed.
        names = [name for name in names
                 if name and len(name) < 120 and all(
                     ch.isalnum() or ch in ".:_-" for ch in name)]
        names.sort(key=lambda name: (not any(
            key in name.lower() for key in ("coder", "code", "qwen")), name))
        return names[0] if names else None
    except (OSError, ValueError, KeyError, TypeError, URLError):
        return None


def commands():
    return [
        sys.executable, "-m", "uvicorn", "app:app",
        "--host", HOST, "--port", str(PORT),
    ], [sys.executable, str(ROOT / "scripts" / "cloud_worker.py")]


def dashboard_port_occupied():
    """Probe only Luna's loopback HTTP port, without starting a worker.

    A listener need not be Luna; refuse to launch a competing process either
    way. This check is advisory and the OS still arbitrates later bind races.
    """
    try:
        with socket.create_connection((HOST, PORT), timeout=0.2):
            return True
    except OSError:
        return False


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
    parser.add_argument("--self-build", action="store_true",
                        help="Use an already installed local Ollama model and "
                             "start autonomous daily draft generation; never install or spend")
    args = parser.parse_args(argv)
    ready = check_readiness()
    if args.check:
        # Local probe only, no personal data, keys or network exposure.
        ready["existing_local_model_available"] = discover_ollama() is not None
        ready["self_build_requires_running_ollama"] = True
        ready["dashboard_port_occupied"] = dashboard_port_occupied()
        print(json.dumps(ready, indent=2))
        return 0 if ready["python_supported"] and not ready["missing_dependencies"] else 1
    if not ready["python_supported"] or ready["missing_dependencies"]:
        print("Luna requires Python 3.11+ and installed requirements.txt dependencies.",
              file=sys.stderr)
        return 1
    if os.environ.get("LUNA_CLOUD_MODE") == "1":
        print("This launcher is localhost-only, not a cloud deployment.", file=sys.stderr)
        return 1
    if dashboard_port_occupied():
        print("Local port 8000 already has a listener. Use the existing Luna "
              "dashboard if it is running, or stop the other application "
              "before launching Luna. No additional worker was started.",
              file=sys.stderr)
        return 3
    env = os.environ.copy()
    env["LUNA_WORKER_ENABLED"] = "1"
    if args.self_build:
        # Reuse an already running Ollama instance and existing model. No
        # software installation, model download, paid service or credentials.
        found = discover_ollama()
        if found is None:
            print("Self-build needs a running local Ollama server with an "
                  "installed model. No model was downloaded or paid for.",
                  file=sys.stderr)
            print("Start Ollama and install a code-capable model separately, "
                  "then retry this command.", file=sys.stderr)
            return 2
        # Explicitly override any inherited cloud model settings: this flag
        # promises local-only development and must never incur API charges.
        env["LUNA_MODEL_URL"] = "http://127.0.0.1:11434/v1"
        env["LUNA_MODEL_NAME"] = found
        env["LUNA_AGENT_MODEL_ENABLED"] = "1"
        env.pop("LUNA_API_KEY", None)
        env.pop("LUNA_AGENT_ALLOW_CLOUD", None)
        print("Using existing local Ollama model: " + found, flush=True)
        env["LUNA_AGENT_AUTO_ENABLED"] = "1"
        # The agent's job queue lives alongside Luna's conversation DB.
        # Back up an existing database consistently before unattended work.
        from luna.launch_guard import snapshot_existing_memory
        from luna.core import DB_PATH
        try:
            if os.environ.get("LUNA_SERVICE_MODE") == "1":
                from luna.backup_schedule import maybe_backup
                result = maybe_backup(DB_PATH, root=ROOT)
                snapshot = result["created"]
            else:
                snapshot = snapshot_existing_memory(DB_PATH, project_root=ROOT)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if snapshot is not None:
            print("Created a private SQLite safety snapshot before self-building.",
                  flush=True)
    if args.auto_drafts:
        if not ready["developer_model_configured_unverified"] and not args.self_build:
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
