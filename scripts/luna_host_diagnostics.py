#!/usr/bin/env python3
"""Read-only Chromebook/Mac host evidence for Luna's supervised handoff.

Does not start/stop a service, read Luna's database, contact any cloud API,
load a model, change GitHub, or print raw process commands/arguments. CPU is
a single platform-visible ps snapshot, not a root-cause diagnosis.
"""
import argparse
import json
import re
import socket
import subprocess
from urllib.request import urlopen

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8000
OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"
CATEGORIES = ("luna_dashboard", "luna_worker", "luna_launcher",
              "ollama", "browser")
_PROCESS_LINE = re.compile(
    r"^\s*\d+\s+([0-9]+(?:\.[0-9]+)?)\s+"
    r"([0-9]+(?:\.[0-9]+)?)\s+(.+)$"
)


def dashboard_port_occupied():
    """A port listener is not necessarily Luna and proves no application health."""
    try:
        with socket.create_connection(
            (DASHBOARD_HOST, DASHBOARD_PORT), timeout=0.3
        ):
            return True
    except OSError:
        return False


def local_ollama_tags():
    """Inspect local tags only; never disclose names or claim a working reply."""
    try:
        with urlopen(OLLAMA_TAGS, timeout=2) as response:
            if response.status != 200:
                return {"http_tags_reachable": False, "model_tags_count": 0}
            raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError("Oversized local tags response")
        payload = json.loads(raw)
        models = payload.get("models", []) if isinstance(payload, dict) else []
        if not isinstance(models, list):
            raise ValueError("Invalid model tags")
        names = [entry.get("name") for entry in models
                 if isinstance(entry, dict) and isinstance(entry.get("name"), str)]
        return {"http_tags_reachable": True, "model_tags_count": len(names)}
    except (OSError, ValueError, TypeError, AttributeError):
        return {"http_tags_reachable": False, "model_tags_count": 0}


def _role(arguments):
    """Inspect locally in memory; never return or log potentially secret args."""
    args = arguments.lower()
    if "scripts/cloud_worker.py" in args:
        return "luna_worker"
    if "uvicorn" in args and "app:app" in args:
        return "luna_dashboard"
    if ("scripts/start_luna_agent.py" in args
            or "scripts/luna_today.py" in args):
        return "luna_launcher"
    if re.search(r"(?:^|[/\\\s])ollama(?:_llama_server)?(?:\s|$)", args):
        return "ollama"
    if re.search(r"(?:^|[/\\\s])(?:google-chrome|chrome|chromium)(?:\s|$)", args):
        return "browser"
    return None


def visible_process_usage():
    """Aggregate only recognized process roles; no raw ps output escapes."""
    empty = {name: {"count": 0, "cpu_percent_sum": 0.0}
             for name in CATEGORIES}
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=", "-o", "%cpu=",
             "-o", "%mem=", "-o", "args="],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode:
            return {"available": False, "roles": empty}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "roles": empty}
    for line in result.stdout.splitlines():
        match = _PROCESS_LINE.match(line)
        if match is None:
            continue
        role = _role(match.group(3))
        if role is None:
            continue
        try:
            percent = float(match.group(1))
        except ValueError:
            continue
        if percent < 0 or percent > 10000:
            continue
        empty[role]["count"] += 1
        empty[role]["cpu_percent_sum"] += percent
    for entry in empty.values():
        entry["cpu_percent_sum"] = round(entry["cpu_percent_sum"], 1)
    return {"available": True, "roles": empty}


def diagnose():
    return {
        "read_only": True,
        "dashboard_port_occupied": dashboard_port_occupied(),
        "ollama": local_ollama_tags(),
        "process_usage": visible_process_usage(),
        "actual_model_reply_verified": False,
        "mac_service_liveness_verified": False,
        "private_database_inspected": False,
        "process_scope": "Visible host/container processes only; ChromeOS browser may be outside Linux container",
        "interpretation": "One ps CPU snapshot is indicative, not an attribution or a load history",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only, redacted host status; never launches Luna"
    )
    parser.add_argument("--check", action="store_true",
                        help="Show private-data-safe diagnostic JSON")
    args = parser.parse_args(argv)
    _ = args.check
    print(json.dumps(diagnose(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
