#!/usr/bin/env bash
# ORBIT verified local launch. Never applies AI-generated code drafts.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Local source changes detected. Refusing to overwrite them."
  exit 1
fi
git pull --ff-only
# Back up the configured SQLite database *before* running tests or launching.
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
python -m compileall -q app.py luna tests
if ! python -m pytest -q -p no:cacheprovider tests; then
  echo "Regression tests failed or pytest is missing. Luna was NOT started."
  exit 1
fi
echo "Local checks passed. Starting Luna on localhost only."
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
