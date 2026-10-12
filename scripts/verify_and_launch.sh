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
  ORBIT_EXPECTED_SHA="$1" python -I - <<'PY'
import json
import os
import sys
import urllib.request
from urllib.error import HTTPError, URLError

commit = os.environ["ORBIT_EXPECTED_SHA"]
# Pin to the trusted workflow *file*, not its non-unique display name.
# A different workflow also called 'ORBIT checks' is not sufficient evidence.
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
    and item.get("path") == ".github/workflows/orbit-checks.yml"
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

# FETCH ONLY: this never checks out or executes newly fetched source.
# Pin the exact remote main revision before inspecting its existing CI
# evidence; do not check out a SHA that has not passed isolated CI.
git fetch --no-tags origin refs/heads/main:refs/remotes/origin/main
verified_target="$(git rev-parse refs/remotes/origin/main)"
verify_ci_commit "$verified_target"

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

# Advance only to the pinned SHA whose successful CI was checked above.
# Never use git pull to check out a moving remote before verification.
# Generated tests are run in isolated GitHub Actions, not with owner secrets.
git merge --ff-only "$verified_target"
if [ "$(git rev-parse HEAD)" != "$verified_target" ]; then
  echo "Checked-out revision changed unexpectedly; refusing launch." >&2
  exit 1
fi
verify_ci_commit "$(git rev-parse HEAD)"
echo "Starting Luna on localhost only."
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
