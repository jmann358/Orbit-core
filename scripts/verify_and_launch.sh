#!/usr/bin/env bash
# ORBIT verified local launch. Never applies AI-generated code drafts.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Local source changes detected. Refusing to overwrite them."
  exit 1
fi
# Require positive CI evidence *before importing application code*.
# A failed update may leave the worktree at a new HEAD; checking only after
# a pull is not enough to prevent the next launch importing that HEAD.
if [ "$(git branch --show-current)" != "main" ]; then
  echo "Use the reviewed main branch to launch Luna." >&2
  exit 1
fi
verify_ci_commit() {
  ORBIT_EXPECTED_SHA="$1" python - <<'PY'
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
}
verify_ci_commit "$(git rev-parse HEAD)"

# This backup must run with the previously reviewed and CI-verified source.
# Never import newly pulled, unverified application modules while the
# owner's memory database is accessible.
# This uses SQLite's online backup API, not a raw copy of a live WAL file.
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

# Newly pulled tests run in isolated GitHub Actions, NOT on the owner's host
# with live memory, GitHub permissions or model credentials.
git pull --ff-only
verify_ci_commit "$(git rev-parse HEAD)"
echo "Starting Luna on localhost only."
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
