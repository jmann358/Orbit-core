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
  backup_name="$(python scripts/backup_luna.py --quiet)"
  echo "Validated local database backup: $backup_name"
fi
python -m compileall -q app.py luna tests
if ! python -m pytest -q -p no:cacheprovider tests; then
  echo "Regression tests failed or pytest is missing. Luna was NOT started."
  exit 1
fi
echo "Local checks passed. Starting Luna on localhost only."
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
