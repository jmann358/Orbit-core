# Cloud-first Luna foundation (not deployed)

This is a **development foundation**, not a cloud service, account, subscription,
or exposed instance. It deliberately keeps the existing localhost experience
unchanged and adds a fail-closed optional authentication boundary and an
independent, durable background worker.

## Architecture

- **Web process:** existing FastAPI app; all HTTP routes protected by
  `CloudOwnerGate` when `LUNA_CLOUD_MODE=1`.
- **Worker process:** `scripts/cloud_worker.py`, sharing a persistent SQLite
  file with the web process; bounded allowlisted jobs only.
- **Storage:** one durable private volume for SQLite, future backups, and
  reviewable memory. Do not put SQLite in an ephemeral container filesystem.
- **Network:** future trusted TLS-terminating reverse proxy with an
  authenticated ASGI scheme, HTTPS, restrictive origin and host handling,
  request limits, and non-public worker. No reverse proxy is installed here.
- **Identity:** future short-lived, revocable owner sessions for browser/iPhone
  are **not yet implemented**. The bearer-token gate is for backend validation
  and API clients, **not** a finished browser login or safe public deployment.
- **Background work:** the worker does not require the browser to remain open.
  It only performs heartbeat and fixed read-only project health tasks. It does
  not edit source, install packages, spend money, invoke models, or contact
  accounts. It is not an independent software developer.

## Safety contract

Cloud mode defaults **OFF**. In cloud mode, requests fail closed unless
`LUNA_OWNER_TOKEN` is a nontrivial secret (at least 32 characters),
`LUNA_PUBLIC_ORIGIN` is a valid HTTPS origin, and the trusted ASGI request
scheme is HTTPS. Every existing HTTP endpoint is protected. Tokens must be
provided through the host's secret manager, never committed to the repository
or pasted into issue comments. HTTPS termination must be configured by an
actual trusted proxy; forwarding headers from the public internet are unsafe.

This implementation intentionally does **not** include a public deployment
manifest, paid provider, default credentials, public listening host, automatic
start, or remote account connection.

## Safe local tests

```bash
python -m pytest -q tests/test_cloud_foundation.py
python scripts/cloud_worker.py --check
```

Both commands are intended to avoid enabling cloud mode, provisioning a
service, or starting continuous work. A local simulated worker may be tested
against a disposable database, never production data.

## Next release gates (separate owner approvals)

1. Reconcile Codex's PR #13 with the conversation-first PR #12 before merging
   shared `app.py`, `luna/core.py`, or test changes. This branch is based
   on `main` to avoid overwriting either branch.
2. Implement secure browser sign-in, session expiry/revocation, CSRF protection,
   login rate limits, and HTTPS proxy trust policy; test unauthorized access
   to all HTTP/WebSocket routes before internet exposure.
3. Add a host-independent encrypted backup and restore drill, database
   durability monitoring, and safe schema migrations.
4. Add a budget-aware approved task scheduler, worker observability and a
   human approval inbox. Keep arbitrary shell commands and auto-code deploys
   disallowed.
5. Choose a hosting provider, verify recurring cost and retention terms, then
   explicitly approve any service creation, secret provisioning, domain, and
   deployment. No step above authorizes those actions.

**Current status:** source + tests prepared for CI; no cloud host exists.
