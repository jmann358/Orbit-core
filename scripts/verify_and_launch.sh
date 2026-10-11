#!/usr/bin/env bash
# ORBIT verified local launch. Never applies AI-generated code drafts.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Local source changes detected. Refusing to overwrite them."
  exit 1
fi
git pull --ff-only
mkdir -p backups
if [ -f luna_local.db ]; then
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p luna_local.db "backups/luna_local-$stamp.db"
  echo "Backed up local database."
fi
python -m compileall -q app.py luna tests
if ! python -m pytest -q -p no:cacheprovider tests; then
  echo "Regression tests failed or pytest is missing. Luna was NOT started."
  exit 1
fi
echo "Local checks passed. Starting Luna on localhost only."
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
