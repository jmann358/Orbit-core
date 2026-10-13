> **THRONE status supersedes older status claims below.** Read [THRONE_STATUS.md](THRONE_STATUS.md), [FLIGHT_PLAN.md](FLIGHT_PLAN.md) and [PLAN_RECONCILIATION.md](PLAN_RECONCILIATION.md) first. The dated entries below are retained evidence, not a live task list.

# Pojo.3.1.0 — remote flight acceptance evidence

**Date:** October 12, 2026. **Branch:** `feature/pojo-3-1-worker-heartbeat-evidence`.
**Evidence status:** candidate CI, not a deployed version or final Flight Plan approval.
**Published application:** `pojo.2` on `main`, SHA
`baf96abff8105b89e7b4c924ff03921f084923b5`.

## Verified implementation milestones

| Area | Reproducible proof | Limitation |
| --- | --- | --- |
| Trusted test state isolation | `tests/test_baseline_env.py`: scrub API tokens, Python/pytest injection settings and host DB path, point subprocess DB to temporary copy | Trusted test code only; NOT a sandbox for untrusted model-written source |
| Atomic delegated backlog queue | `tests/test_backlog_atomic.py`: crash injection, concurrent ticks, budget and tampered kind tests | Only allowlisted fixed job handlers |
| Draft review honesty | `tests/test_draft_review_coverage.py`: unchecked 13th block cannot appear fully syntax-validated | AST parse alone cannot establish security or correctness |
| SQLite lifetime | `tests/test_core_connections_managed.py`: immediate close, rollback after exception, job creation after reopen | Actual owner's SQLite/WAL restore needs host evidence |
| Launcher backup messaging | `tests/test_launcher_backup_status.py`: distinguish created, reused and missing database | Backup restore on real Mac not tested |
| Chat to real worker result | `tests/test_live_server_smoke.py::test_real_http_chat_worker_receipt_survives_process_restart` starts localhost Uvicorn, creates a chat-requested job, observes actual worker completion and proves the same result is saved after restart | No model inference, browser automation or cross-device use |
| Ordered approved goal | `tests/test_live_server_smoke.py::test_live_multistep_goal_runs_only_after_approval_and_survives_restart`: no child jobs before explicit approval, two distinct sequential real worker steps, persisted signed-off result after restart, duplicate replay refused | Predefined safe recipe steps, not open-ended autonomous tool selection |
| In-context approval | `tests/test_inline_goal_approval.py`: home links to real goal, atomic approve/reject, duplicate approval fails | DOM presence is not evidence of actual iPhone browser UX |
| Honest worker status | `tests/test_worker_heartbeat_status.py`: embedded job thread writes only state and timestamp; stale/paused/attention status available in `/agent/worker` and home | A recent heartbeat is *observed metadata*, not independent liveness proof |
| Runner diagnosis | `scripts/bootstrap_safe_runner.py`, `tests/test_runner_readonly_diagnostic.py` | Read-only Linux prerequisite inventory; Mac secure executor NOT installed or enabled |

## Historical PR reconciliation

- **PR #1** contains 111 changed paths. Of those, 23 paths already exist
  in current main and 88 are branch-only (39 non-test, 49 tests). This
  inventory is filename-based and does not prove semantic feature overlap.
- The small truthful draft-screening repair from **PR #2** is incorporated
  with new regression coverage; do not merge old PR #2 wholesale.
- Safe read-only runner diagnostic from **PR #3** has been recovered without
  its dangerous, unverified untrusted execution path.
- Historical runner executor, repair orchestrator, watchdog, sensitivity
  contracts, and activity history need separate security- and trust-boundary
  review. PR #1's broken CI and branch conflicts mean no wholesale merge.

## Strictly not certified / owner gates

1. A genuine local model inference call on the Mac, quality and cost
   restrictions, model-independent long-term memory, and conversation resilience.
2. Safe execution/test/repair/rollback for model-generated code on the
   actual platform. Trusted baseline tests **must never be used for this**.
3. WAL-consistent private database transfer from the existing Chromebook,
   owner-key-controlled backup integrity, Mac service startup/recovery and
   power/sleep behavior with one authoritative database.
4. Authenticated and revocable phone/tablet pairing before any LAN or Internet
   exposure. Today's dashboard has no local bearer/cookie authentication.
5. Contextual approvals for broader non-recipe missions; the existing
   allowlist is intentionally narrow, not a general computer-control agent.
6. Cross-device interaction, notifications, voice, and expressive UI
   verified on real devices.
7. Independent code/security review beyond GitHub's matrix tests.
8. The reviewed Flight Plan 1.0-RC and publication of any pojo.3 release
   require separately recorded owner signoff.

No owner data, credentials, device network endpoints or actual SQLite
backups were copied to GitHub in this work. No merge, deployment, paid model
call, host service installation or new runtime authorization was performed.

## Evidence scope rule

A CI-green branch may be described as **test-passing for the enumerated
scenarios only**. Do not label it "Mac-ready", "securely self-developing",
"live model connected", or "fully autonomous" before the separate acceptance
gates actually pass.
