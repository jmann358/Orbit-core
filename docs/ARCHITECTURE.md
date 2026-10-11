# ORBIT architecture

ORBIT is the control room. Luna is the central assistant/coordinator inside it. Model providers are replaceable reasoning backends; Luna's identity, permissions, project records, continuity, and governance stay in ORBIT.

## Current local runtime
- **FastAPI dashboard (`app.py`)** — localhost-only control center, chat, review queues, development status, readiness, activity, backups, and safe diagnostics.
- **SQLite state (`luna/core.py`)** — local chat history plus durable project/task records. Secrets are not intentionally stored as credentials here.
- **Background worker** — executes only fixed allowlisted job kinds, advances approved bounded goals, reconciles backlog work, and emits a durable heartbeat.
- **Provider adapters** — explicit local or supported HTTPS model endpoints configured through environment variables. Provider choice is not Luna's identity.

## Memory and continuity
- Explicit memory suggestions are opt-in and remain pending until owner approval.
- Project notes and technical decisions use separate review/provenance paths.
- Long conversations can create deterministic local checkpoint summaries without an extra model call.
- Current-session continuity may use its own checkpoint; cross-session context uses only owner-approved summaries.
- Local history search excludes messages detected as sensitive.
- Sensitive-looking intake is blocked before normal chat persistence/model handling while the future quarantine broker is unavailable.

## Development safety pipeline
1. Luna/planning tools prepare bounded proposals or drafts.
2. Static review restricts paths and validates expected base hashes / Python parsing.
3. Only the narrow allowlist can enter the isolated regression runner.
4. The runner uses an owner-approved immutable local container image, no network, read-only host mount, unprivileged user, dropped capabilities, bounded resources, and fixed test targets.
5. Repair validation is limited to two attempts.
6. Passing validation means **ready for review**, not permission to modify live source.
7. Automatic code application, deployment, and merge remain disabled.

The legacy workshop temporary directory is staging/static validation only; it is not considered an isolation boundary.

## Permissions and autonomy
- Tier-1 deterministic diagnostics can run automatically within bounded schedules.
- Temporary `prepare_patch` / `run_tests` grants require owner authorization and expire.
- Code application, security changes, spending, access expansion, destructive actions, remote exposure, and deployment are not delegated.
- Unattended model drafting is disabled by default and, when explicitly enabled, is restricted to local model endpoints with a small daily call budget.
- Goals and backlog entries dispatch only allowlisted job kinds.

## Observability and recovery
- Unified Activity timeline exposes metadata only; sensitive payloads and private watchdog data are excluded.
- Worker heartbeat distinguishes starting, working, idle, attention, stopped, and stale states.
- Readiness/doctor checks report database integrity, runner/model prerequisites, worker state, backup state, and safe recommendations.
- Maintenance audit detects stale jobs, expired grants, stuck dispatches, stale worker state, and high-priority unresolved requests without mutating them.
- Validated local SQLite backups are supported; restore remains deliberate/planning-oriented.
- Copy safe status emits a sanitized support snapshot for troubleshooting.

## GitHub collaboration
- GitHub Actions run regression checks on sprint work.
- Repository changes stay on reviewable branches/PRs; no automatic merge.
- The current ChatGPT bridge is user-mediated. ORBIT does not claim a persistent autonomous ChatGPT-to-Luna background conversation.
- Machine-readable relay/status contracts do not themselves grant execution authority.

## Owner-only security boundary (not operational yet)
The future password/sensitive-information vault and private investigator/watchdog must run outside Luna's runtime authority.

Requirements:
- separate OS identity/service and storage permissions;
- vault decryption keys unavailable to Luna;
- no generic Luna tool path into vault or watchdog storage;
- quarantine intake before Luna/model context where possible;
- owner-authenticated preserve/delete/release/rule decisions;
- watchdog logs/configuration not queryable or mutable by Luna;
- minimal metadata only in shared security events.

Repository contracts and threat-model documents are foundations, **not** proof that the vault/watchdog are isolated today.

## Intended deployment path
Current development may run in ChromeOS Linux. The intended always-on home is the Mac mini, with secure authenticated access from iPhone/other authorized devices added later. Until authentication and pairing are implemented, keep ORBIT bound to localhost only.
