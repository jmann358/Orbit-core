# ORBIT · Luna

ORBIT is a local-first, provider-independent assistant ecosystem. Luna is its conversational coordinator.

## Current capabilities

- Private localhost FastAPI dashboard and persistent SQLite chat sessions.
- Optional OpenAI-compatible model connection through environment variables.
- Approval-gated memory candidates and project notes.
- **Opt-in memory suggestions**: explicit user statements beginning with “Remember that…” can become pending suggestions; sensitive-looking strings are filtered, repeated suggestions are deduplicated, and approval is required before inclusion in Luna's context. This is a heuristic, not comprehensive privacy protection.
- Durable allowlisted task inbox with a background worker and restart recovery.
- Read-only health/GitHub status checks and self-improvement roadmap proposals.
- Development workshop: drafts **unapplied** code proposals, runs conservative text screening, and can attempt one revision. Saved drafts can be reviewed but are never applied or executed by the workshop.
- GitHub Actions regression checks.

## Verified update and launch

Stop the currently running server first. From the project directory run `bash scripts/verify_and_launch.sh`. The script pulls only fast-forward changes, backs up the default SQLite database, compiles Python files, runs regression tests, and starts Luna **only if the checks pass**. It requires `pytest` to be installed (`python -m pip install pytest`). If you configured `LUNA_DB_PATH` to a custom location, back up that database separately.

## Start locally

Use Python 3.11+ (GitHub CI tests 3.13).

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 on the **same machine**. Keep the bind address at 127.0.0.1: there is **no authentication** for remote users yet.

Configure the model separately using `LUNA_MODEL_URL`, `LUNA_MODEL_NAME`, and `LUNA_API_KEY` in the local environment. Do not commit credentials. SQLite is stored in `luna_local.db` by default; back it up before migrating hosts.

## What is *not* implemented

- Remote phone/iPad access with authentication.
- Arbitrary agent tool use, real sandboxed code execution, automated patch application or safe self-deployment.
- Autonomous source code changes without review.
- Verified semantic correctness of AI-generated patches.
- Automatic identification of arbitrary conversational memories. Memory suggestions are intentionally narrow and opt-in.

## Development workflow

Development proposals are drafts, not applied changes. The quality gate flags some common issues but **cannot** certify security, functionality, or syntax of unified diffs. GitHub CI validates repository code, not generated draft patches. Routine changes should be batched, reviewed and tested before installing locally.

See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), and [development policy](DEVELOPMENT_POLICY.md).
