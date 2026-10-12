#!/usr/bin/env python3
"""Install Luna as a private, restartable macOS login service.

Nothing here installs software, downloads models, exposes a port, moves
conversation data, changes permissions, enables paid APIs, or grants GitHub
access. Run after the separately approved local setup has succeeded.
"""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LABEL = "com.orbit.luna"
PLIST_NAME = LABEL + ".plist"


def service_file(home=None):
    home = Path.home() if home is None else Path(home)
    return home / "Library" / "LaunchAgents" / PLIST_NAME


def plist_config(root=ROOT, home=None):
    root = Path(root).resolve()
    home = Path.home() if home is None else Path(home)
    python = root / ".venv" / "bin" / "python"
    launcher = root / "scripts" / "start_luna_agent.py"
    logs = home / "Library" / "Logs" / "ORBIT-Luna"
    return {
        "Label": LABEL,
        "ProgramArguments": [str(python), str(launcher), "--self-build"],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "StandardOutPath": str(logs / "luna.stdout.log"),
        "StandardErrorPath": str(logs / "luna.stderr.log"),
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "PYTHONUNBUFFERED": "1",
            "LUNA_SERVICE_MODE": "1",
        },
    }


def require_mac():
    if sys.platform != "darwin":
        raise ValueError("Autostart can only be installed on the Mac home base")


def preflight(root=ROOT):
    root = Path(root)
    needed = (root / ".venv" / "bin" / "python",
              root / "scripts" / "start_luna_agent.py")
    missing = [str(path) for path in needed if not path.is_file()]
    if missing:
        raise ValueError("First run Luna's one-time setup: missing " +
                         ", ".join(missing))
    if not shutil.which("launchctl"):
        raise ValueError("macOS launchctl is unavailable")
    # Never install a restarting broken launcher without an existing model.
    from scripts.start_luna_agent import discover_ollama
    if not discover_ollama():
        raise ValueError("Ollama must be running with an installed local model")


def _launchctl(*args, allow_error=False):
    process = subprocess.run(["launchctl", *args], capture_output=True,
                             text=True, timeout=20)
    if process.returncode and not allow_error:
        raise ValueError("macOS service operation failed; inspect launchctl locally")
    return process.returncode == 0


def install(root=ROOT, home=None):
    require_mac()
    preflight(root)
    root = Path(root).resolve()
    home = Path.home() if home is None else Path(home)
    target = service_file(home)
    if target.is_symlink():
        raise ValueError("Refusing a symlinked LaunchAgent file")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    logdir = home / "Library" / "Logs" / "ORBIT-Luna"
    if logdir.is_symlink():
        raise ValueError("Refusing a symlinked Luna log directory")
    logdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    expected = plist_config(root, home)
    if target.exists():
        try:
            with target.open("rb") as handle:
                existing = plistlib.load(handle)
        except (OSError, ValueError, TypeError):
            raise ValueError("Existing Luna LaunchAgent is invalid") from None
        if existing.get("Label") != LABEL:
            raise ValueError("Refusing to replace a different LaunchAgent")
        # Preserve unknown or owner-customized plist content rather than
        # silently rewriting an existing service configuration.
        if existing != expected:
            raise ValueError("Existing Luna LaunchAgent differs; review manually")
    else:
        with target.open("xb") as handle:
            plistlib.dump(expected, handle)
        os.chmod(target, 0o600)
    domain = "gui/" + str(os.getuid())
    _launchctl("bootout", domain + "/" + LABEL, allow_error=True)
    _launchctl("bootstrap", domain, str(target))
    _launchctl("kickstart", "-k", domain + "/" + LABEL)
    return target


def uninstall(home=None):
    require_mac()
    path = service_file(home)
    if path.is_symlink():
        raise ValueError("Refusing a symlinked LaunchAgent file")
    _launchctl("bootout", "gui/" + str(os.getuid()) + "/" + LABEL,
               allow_error=True)
    if path.is_file():
        with path.open("rb") as handle:
            content = plistlib.load(handle)
        if content.get("Label") != LABEL:
            raise ValueError("Refusing to remove a different LaunchAgent")
        path.unlink()
    # Uninstall never deletes database, backup, model, app, or logs.


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage Luna on macOS login")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true")
    group.add_argument("--uninstall", action="store_true")
    group.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.install:
            path = install()
            print("Luna autostart installed:", path)
            print("Chat on this Mac: http://127.0.0.1:8000")
            print("Agent Studio: http://127.0.0.1:8000/agent/studio")
            print("Restarts after login and if her process exits.")
        elif args.uninstall:
            uninstall()
            print("Autostart removed. Luna's data was preserved.")
        else:
            require_mac()
            path = service_file()
            print("LaunchAgent installed:", path.is_file())
            print("Running:", _launchctl("print",
                  "gui/" + str(os.getuid()) + "/" + LABEL, allow_error=True))
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
