# ORBIT safe development sprint

This branch is a reviewable, unmerged development sprint. Passing tests do not grant merge or deployment authority.

## Current verified direction
- Existing trusted source can run the normal regression suite.
- Proposed replacements for the narrow development allowlist can be validated in the Podman isolation runner.
- The local safe-runner bootstrap was successfully smoke-tested on the owner machine on 2026-10-11: the fixed regression target passed, the host source stayed unchanged, and automatic application/merge remained disabled.
- Repairs are bounded to two validation attempts, then stop for attention.
- Generated code is **never automatically applied to live source**.
- GitHub changes remain reviewable branch/PR work; merges require owner approval.
- Technical memory is separate from personal memory. Cross-session conversation continuity requires owner-approved summaries.
- Obvious sensitive chat payloads are blocked before normal Luna persistence/model handling while the owner-only vault broker is not operational.
- Routine local diagnostics, planning, heartbeat, maintenance audit, readiness checks, validated backups, and activity reporting can run without granting Luna new privileges.
- Paid actions, credentials, access expansion, security-policy changes, remote exposure, destructive actions, and deployment still require owner approval.

## Isolation status
The previous temporary-directory-only workshop remains a static staging tool and is **not** treated as a sandbox.

The separate isolated runner now uses:
- a locally approved immutable container image ID;
- Podman/Docker runtime preflight;
- no network;
- read-only host mount;
- unprivileged container user;
- dropped capabilities / no-new-privileges;
- bounded memory/PID/time limits;
- fixed regression targets only;
- a temporary `run_tests` grant;
- no shell string execution, live source write, auto-apply, or merge.

This is a narrow regression validator, not general-purpose arbitrary code execution.

## Continuity and observability
- Long conversations can create local pending checkpoints without an extra model call.
- Only owner-approved checkpoints become cross-session model context.
- Local history search hides messages caught by the sensitivity classifier.
- The Activity tab combines safe job/agent/sandbox/goal/bridge/request metadata.
- The background worker emits a durable heartbeat so ORBIT can distinguish working, idle, stopped, and stale states.
- The Readiness panel and `scripts/luna_doctor.py` expose safe capability status without returning credentials.
- The Overview maintenance audit detects stale jobs, expired grants, stuck dispatches, stale worker state, and unresolved high-priority requests without mutating them.
- “Copy safe status” produces a sanitized support snapshot with no conversation bodies, code, credentials, vault data, or private watchdog data.

## Data protection still pending
The owner-only password/sensitive-information vault and truly Luna-blind watchdog require an OS-enforced boundary on the final host. Their contracts and threat model exist, but they are **not operational secure stores yet**. Do not place real passwords or vault secrets in the repository or Luna databases.

## Verification
Before merge:
1. Require green GitHub regression workflows on the current head.
2. Run the trusted local full suite on the intended host.
3. Re-run the safe-runner smoke test after container/runtime changes.
4. Confirm backups and restore planning.
5. Keep automatic code application and merge disabled until separately approved.
