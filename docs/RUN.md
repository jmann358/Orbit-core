# Running ORBIT · Luna locally

The current build is a local-first development system. The authoritative version is stored in the repository `VERSION` file.

## Recommended verified launch
From the repository directory:

```bash
source .venv/bin/activate
bash scripts/verify_and_launch.sh
```

The verified launcher refuses dirty tracked source, pulls only fast-forward changes, creates a local database backup when applicable, compiles Python, runs the regression suite, and starts Luna on `127.0.0.1:8000` only if verification succeeds.

Open `http://127.0.0.1:8000` on the same computer.

## Read-only readiness doctor
To see what is ready or blocked without changing anything:

```bash
source .venv/bin/activate
python scripts/luna_doctor.py
```

Use `python scripts/luna_doctor.py --json` for the safe machine-readable form. The doctor reports capability state, not credentials.

## Isolated regression runner
The narrow Luna code-validation runner uses a locally built immutable container image and a temporary `run_tests` grant. Podman is the preferred current runtime.

After installing Podman once, bootstrap/re-verify the isolated runner with:

```bash
source .venv/bin/activate
python scripts/bootstrap_safe_runner.py
```

A successful result must report a passed smoke test, `live_files_changed: false`, `auto_apply: false`, and `merge_allowed: false`.

## Optional terminal activity feed
While the ORBIT server is running:

```bash
python scripts/watch_luna_activity.py
```

This polls only the localhost sanitized activity timeline. It does not expose conversation bodies, code candidate contents, credentials, vault data, or private watchdog data.

## Dashboard tools
- Overview: readiness, maintenance audit, validated local backup controls, pending decisions, and Copy safe status.
- Activity: current worker state and privacy-filtered durable activity metadata.
- Memory: approval-gated memory suggestions plus reviewable conversation-continuity checkpoints and local history search.
- Sprint/Development: technical planning context, bounded draft review, GitHub checks, and isolated validation status.
- Testing: local health and fixed-scope regression checks.

## Model configuration
Without a model configured, persistence, readiness, memory review, local diagnostics, and other deterministic tools still work.

For a local OpenAI-compatible endpoint, set `LUNA_MODEL_URL` and `LUNA_MODEL_NAME` before launch. Localhost HTTP is allowed by policy. For a supported HTTPS cloud provider, also provide `LUNA_API_KEY` in the local environment; never commit it or paste it into project memory.

Unattended model drafting is separately gated and local-endpoint-only. Automatic cloud model calls are not authorized by that gate.

## Security rules
- Keep the server bound to `127.0.0.1`; authenticated remote phone/iPad access is not implemented yet.
- Do not port-forward or publicly expose this dashboard.
- Sensitive-looking chat payloads are blocked before ordinary Luna persistence/model handling where the current classifier detects them, but classification is not perfect.
- The owner-only credential/sensitive-information vault is **not operational yet**. Do not use the repository or Luna SQLite database as a password manager.
- The private watchdog contract exists, but true Luna-blind storage still requires OS-level isolation on the final host.
- Generated code may be drafted and narrowly validated, but automatic live-source application and automatic merge remain disabled.

## Local backups
The dashboard/launcher can create validated local SQLite backups. Restore is planning-only: do not overwrite the live database while Luna is running. Keep backup storage private because it may contain conversation data.
