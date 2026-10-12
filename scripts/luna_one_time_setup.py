#!/usr/bin/env python3
"""One-time, zero-subscription Mac setup for Luna's local self-building loop.

Run explicitly on the Mac mini. May install Python packages, Ollama through
an existing Homebrew installation and a locally stored model. It does NOT
enable paid APIs, cloud hosting, GitHub write access, remote networking,
automatic code merging, or any changes to Luna's private memory.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen2.5-coder:7b"
MODEL_MIN_FREE_BYTES = 8 * (1024 ** 3)


def run(*command, timeout=None):
    result = subprocess.run(command, cwd=ROOT, check=False, timeout=timeout)
    if result.returncode:
        raise RuntimeError("A setup command failed; no paid services were enabled")


def require_mac():
    if sys.platform != "darwin":
        raise RuntimeError(
            "This is the always-on Mac mini setup. On Linux, use "
            "python scripts/start_luna_agent.py --self-build after installing "
            "and starting Ollama with a local model."
        )


def existing_python():
    return ROOT / ".venv" / "bin" / "python"


def prepare_python():
    if sys.version_info < (3, 11):
        raise RuntimeError("Requires Python 3.11+. Install a current Python "
                           "release, then re-run this one-time setup.")
    python = existing_python()
    if not python.is_file():
        run(sys.executable, "-m", "venv", str(ROOT / ".venv"))
    # Only previously reviewed project dependencies are installed. No
    # provider keys, model subscriptions or external accounts are created.
    run(str(python), "-m", "pip", "install", "-r",
        str(ROOT / "requirements.txt"), timeout=900)
    return python


def model_names():
    try:
        with urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            if response.status != 200:
                return None
            payload = json.load(response)
        if not isinstance(payload, dict):
            return None
        return [
            entry["name"] for entry in payload.get("models", [])
            if isinstance(entry, dict) and isinstance(entry.get("name"), str)
        ]
    except (OSError, ValueError, TypeError, URLError):
        return None


def ensure_ollama_command():
    command = shutil.which("ollama")
    if command:
        return command
    brew = shutil.which("brew")
    if not brew:
        raise RuntimeError("Ollama is not installed and Homebrew isn't available. "
                           "Install the free Ollama Mac application from "
                           "https://ollama.com/download/mac and re-run setup.")
    print("Installing free Ollama through the existing Homebrew installation...",
          flush=True)
    run(brew, "install", "ollama", timeout=900)
    return shutil.which("ollama") or "/opt/homebrew/bin/ollama"


def start_model_server():
    if model_names() is not None:
        return
    brew = shutil.which("brew")
    if brew:
        installed = subprocess.run([brew, "list", "--versions", "ollama"],
                                   capture_output=True, text=True)
        if installed.returncode == 0:
            run(brew, "services", "start", "ollama", timeout=60)
    if model_names() is None:
        # Works for the official Ollama.app distribution, when installed.
        subprocess.run(["open", "-a", "Ollama"], capture_output=True, timeout=15)
    for _ in range(20):
        if model_names() is not None:
            return
        time.sleep(1)
    raise RuntimeError("Ollama was installed but did not start. Open the Ollama "
                       "Mac application and re-run this setup.")


def ensure_local_model(ollama):
    existing = model_names()
    if existing is None:
        raise RuntimeError("Ollama isn't reachable locally")
    if any("coder" in name.lower() for name in existing):
        print("Using an already installed coding model; no download.", flush=True)
        return
    free = shutil.disk_usage(ROOT).free
    if free < MODEL_MIN_FREE_BYTES:
        raise RuntimeError("The Mac needs at least 8 GB of available disk "
                           "space before downloading the free coding model")
    print("Downloading a free local coding model to this Mac; "
          "no subscription or API key required.", flush=True)
    run(ollama, "pull", MODEL, timeout=3600)
    if not model_names():
        raise RuntimeError("Model download did not verify as available")


def verify_local_inference():
    """Actually exercise existing free local inference, not just list tags."""
    available = model_names() or []
    names = [name for name in available if isinstance(name, str) and name]
    names.sort(key=lambda name: (not any(
        tag in name.lower() for tag in ("coder", "code", "qwen")), name))
    if not names:
        raise RuntimeError("No Ollama model is installed")
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps({
            "model": names[0],
            "prompt": "Reply with the word OK.",
            "stream": False,
            "options": {"num_predict": 12},
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            answer = json.load(response)
    except (OSError, ValueError, TypeError, URLError):
        raise RuntimeError("The installed local AI model is not responding. "
                           "Check Ollama and retry setup.") from None
    if (not isinstance(answer, dict)
            or not isinstance(answer.get("response"), str)
            or not answer["response"].strip()):
        raise RuntimeError("The local AI model did not return a usable reply")
    print("Verified a real local AI model response without any cloud API.",
          flush=True)


def ensure_github_login():
    """Optional one-time owner authorization, never collect or print tokens."""
    gh = shutil.which("gh")
    if not gh:
        brew = shutil.which("brew")
        if not brew:
            raise RuntimeError("GitHub draft PRs require GitHub CLI. Install gh "
                               "or omit --enable-draft-prs for local-only work.")
        print("Installing free GitHub CLI through Homebrew...", flush=True)
        run(brew, "install", "gh", timeout=900)
        gh = shutil.which("gh") or "/opt/homebrew/bin/gh"
    status = subprocess.run([gh, "auth", "status", "--hostname", "github.com"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if status.returncode:
        print("One-time GitHub authorization is needed for Luna to submit "
              "draft pull requests. The GitHub CLI may request the 'repo' "
              "OAuth scope, which can cover other repositories; Luna's "
              "publisher is coded to target ORBIT only.", flush=True)
        run(gh, "auth", "login", "--hostname", "github.com",
            "--web", "--scopes", "repo", timeout=900)
    status = subprocess.run([gh, "auth", "status", "--hostname", "github.com"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if status.returncode:
        raise RuntimeError("GitHub login could not be verified; no draft PR "
                           "permissions were enabled")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare Mac for Luna's self-building")
    parser.add_argument("--check", action="store_true",
                        help="Report blockers without installing anything")
    parser.add_argument("--enable-draft-prs", action="store_true",
                        help="Authorize GitHub CLI once so Luna can create draft "
                             "review PRs automatically; no merges or deployments")
    args = parser.parse_args(argv)
    try:
        require_mac()
        if args.check:
            print(json.dumps({
                "python_supported": sys.version_info >= (3, 11),
                "venv_python_exists": existing_python().is_file(),
                "ollama_installed": shutil.which("ollama") is not None,
                "ollama_running_with_model": bool(model_names()),
                "launchagent_exists": (
                    Path.home() / "Library" / "LaunchAgents"
                    / "com.orbit.luna.plist"
                ).is_file(),
                "no_cloud_credentials_required": True,
                "phone_access_enabled": False,
            }, indent=2))
            return 0
        print("Preparing local Luna. Only free local software will be installed.",
              flush=True)
        python = prepare_python()
        ollama = ensure_ollama_command()
        start_model_server()
        ensure_local_model(ollama)
        verify_local_inference()
        if args.enable_draft_prs:
            ensure_github_login()
        command = [str(python), str(ROOT / "scripts" / "luna_mac_service.py"),
                   "--install"]
        if args.enable_draft_prs:
            command.append("--enable-draft-prs")
        run(*command)
        print("Luna is configured for supervised daily development drafts.")
        print("Chat: http://127.0.0.1:8000")
        print("Agent Studio: http://127.0.0.1:8000/agent/studio")
        print("She will restart after macOS login and if the agent exits.")
        if args.enable_draft_prs:
            print("GitHub draft PR publishing enabled for ORBIT. "
                  "Owner review and merge are still required.")
        else:
            print("Draft PR publishing requires an explicit separate GitHub "
                  "opt-in; local development drafts are still automatic.")
        print("Keep the Mac awake to allow unattended work. "
              "Secure phone access is not activated.")
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
