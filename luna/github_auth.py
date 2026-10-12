"""Optional GitHub CLI credentials for Luna's draft-only ORBIT PR workflow.

Uses an owner's existing local gh login when separately enabled.
Never stores, prints, logs or sends GitHub credentials to model prompts.
Tokens are used only by Luna's fixed-repository PR publisher.
"""
import os
import re
import shutil
import subprocess


def token_for_draft_pr(environ=None):
    env = os.environ if environ is None else environ
    key = env.get("LUNA_GITHUB_TOKEN") or ""
    if key:
        return key
    if env.get("LUNA_GITHUB_USE_GH_CLI") != "1":
        return ""
    gh = shutil.which("gh")
    if not gh:
        return ""
    try:
        proc = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode:
        return ""
    token = proc.stdout.strip()
    # Exclude control characters or unexpected output; never return stderr.
    if not 8 <= len(token) <= 2048 or not re.fullmatch(r"[A-Za-z0-9_\-]+", token):
        return ""
    return token
