#!/usr/bin/env python3
"""One straightforward, localhost-only entry point for Luna on Chromebook/Linux.

Uses a previously installed, running Ollama model for safe self-build when
available. Otherwise opens the real dashboard and worker, clearly reporting
that AI model replies and design generation are unavailable until configured.

Does not install software, download models, expose network ports, spend money,
write credentials, merge, deploy, or bypass owner approvals.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import start_luna_agent  # noqa: E402
from luna.model_connection import inspect_model_configuration  # noqa: E402


def diagnose():
    ready = start_luna_agent.check_readiness()
    discovered = start_luna_agent.discover_ollama()
    model = inspect_model_configuration()
    return {
        "python_supported": ready["python_supported"],
        "missing_dependencies": ready["missing_dependencies"],
        "local_model_detected": discovered is not None,
        "model_connection_state": "local_model_available" if discovered else model["state"],
        "dashboard": "http://127.0.0.1:8000",
        "workspace": "http://127.0.0.1:8000/agent/studio",
        "remote_phone_access": False,
        "model_name_disclosed": False,
        "read_only": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Open Luna with a simple owner dashboard and independent local worker"
    )
    parser.add_argument("--check", action="store_true",
                        help="Inspect prerequisites without starting Luna")
    args = parser.parse_args(argv)
    ready = diagnose()
    if args.check:
        print(json.dumps(ready, indent=2))
        return 0 if ready["python_supported"] and not ready["missing_dependencies"] else 1
    if not ready["python_supported"]:
        print("Luna needs Python 3.11 or newer.", file=sys.stderr)
        return 1
    if ready["missing_dependencies"]:
        print("Some required packages are missing: " +
              ", ".join(ready["missing_dependencies"]), file=sys.stderr)
        print("From Orbit-core run: python -m pip install -r requirements.txt",
              file=sys.stderr)
        return 1
    print("\nLuna's simple home screen: http://127.0.0.1:8000", flush=True)
    print("This address opens on your Chromebook, not your phone.", flush=True)
    if ready["local_model_detected"]:
        print("Existing free local model found. Starting Luna's bounded developer "
              "worker and conversation interface.", flush=True)
        return start_luna_agent.main(["--self-build"])
    if ready["model_connection_state"] == "configured_unverified":
        print("An AI provider is configured, but real model replies remain unverified. "
              "Luna's development model will not be enabled automatically.", flush=True)
    else:
        print("No working local Ollama model was detected. Luna's dashboard, saved "
              "conversations and review queue can run; real AI answers and design "
              "generation will require a configured working model.", flush=True)
    print("Opening the available app and independent worker without paid services.",
          flush=True)
    return start_luna_agent.main([])


if __name__ == "__main__":
    raise SystemExit(main())
