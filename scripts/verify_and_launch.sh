#!/usr/bin/env bash
# ORBIT verified local launch. Never applies AI-generated code drafts.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Local source changes detected. Refusing to overwrite them."
  exit 1
fi
# This backup must run with the source that is ALREADY checked out.
# Never import newly pulled, unverified application modules while the
# owner's memory database is accessible.
# Back up the configured SQLite database before pulling or running tests.
# This uses SQLite's online backup API, validates integrity and never copies a
# live WAL database with an unsafe raw filesystem copy.
python - <<'PY'
from pathlib import Path
from luna.core import DB_PATH
from luna.launch_guard import snapshot_existing_memory
snapshot = snapshot_existing_memory(DB_PATH, project_root=Path.cwd())
if snapshot is not None:
    print("Consistent private SQLite backup verified.")
else:
    print("No existing database to back up.")
PY
# GitHub Actions runs new tests in a disposable cloud runner with no
# access to the owner's memory, local files, API keys or host credentials.
# Never execute newly pulled tests or app imports on the owner's host before
# the exact commit has an isolated, successful main-branch CI run.
if [ "$(git branch --show-current)" != "main" ]; then
  echo "Use the reviewed main branch to launch Luna." >&2
  exit 1
fi
git pull --ff-only
export ORBIT_EXPECTED_SHA
ORBIT_EXPECTED_SHA="$(git rev-parse HEAD)"
python - <<'PY'
import json
import os
import sys
import urllib.request
from urllib.error import HTTPError, URLError

commit = os.environ["ORBIT_EXPECTED_SHA"]
url = ("https://api.github.com/repos/jmann358/Orbit-core/actions/runs?"
       "head_sha=" + commit + "&event=push&per_page=25")
request = urllib.request.Request(
    url,
    headers={"Accept": "application/vnd.github+json",
             "User-Agent": "ORBIT-Verified-Launch"},
)
try:
    with urllib.request.urlopen(request, timeout=12) as response:
        runs = json.load(response).get("workflow_runs", [])
except (HTTPError, URLError, ValueError, OSError):
    print("Cannot verify GitHub CI for this commit; refusing launch.", file=sys.stderr)
    sys.exit(1)
verified = any(
    item.get("head_sha") == commit
    and item.get("head_branch") == "main"
    and item.get("name") == "ORBIT checks"
    and item.get("status") == "completed"
    and item.get("conclusion") == "success"
    for item in runs if isinstance(item, dict)
)
if not verified:
    print("No successful isolated CI run found for this main commit; "
          "refusing launch until verification passes.", file=sys.stderr)
    sys.exit(1)
print("Exact main commit passed isolated GitHub CI. No local tests executed.")
PY
echo "Starting Luna on localhost only."
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
