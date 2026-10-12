# Pojo.3.1.0 — remote engineering and legacy-sprint reconciliation

**Date:** 2026-10-12. **Review status:** all current changes remain unmerged, draft PRs.
**Public deployment readiness:** NOT CERTIFIED. **Software on main:** pojo.2.

## Work completed without access to the owner's Mac

| PR | Status and scope |
| --- | --- |
| #32 | Isolated the trusted baseline check's subprocess environment from owner credentials/production SQLite and called out that tests are not an OS security sandbox. Independently CI-green. |
| #33 | Atomic backlog authorization/budget/job/event/link transaction with crash and concurrency tests. Independently CI-green. |
| #34 | Shared integration candidate containing #32/#33, historical PR #2's truthful static-review fix, and accurate Mac backup startup status. CI-green. |
| #35 | Managed SQLite connection lifetime in existing `with core.connect() as db` callers; commits, rollbacks and closes, tested independently. CI-green. |
| #36 | Durable read-only job/goal receipts and direct chat/dashboard result links. End-to-end test starts *actual local Uvicorn process*, queues a health check from natural language, lets the actual worker finish, restarts the server, and verifies the same saved receipt. CI-green. |

**Most recent verification:** PR #36 push run `38273232323`:
403 passed / 13 existing warnings on Python 3.11 and 403 passed / 13 existing warnings on Python 3.13.
This certifies **the tested runner scenario**, not the owner's Mac hardware, live model, cloud access or all 34 Flight Plan tests.

## Legacy Sprint #1 exact file-level review

At PR #1's recorded 111 changed paths, relative to the pinned pojo.2 main tree:
- **23 paths are already present on main** (not necessarily identical behavior; inspect diffs).
- **88 changed paths are absent from main**: 49 are historical tests and 39 are code/config/docs/scripts.
- `luna/continuity.py`, `tests/test_continuity.py` and other paths marked added in historical PR are also now present on main; path status in an old PR is not a gap verdict.
- PR #1 is **conflicted and CI-failing**: `test_maintenance_job_reports_attention_without_mutating` expects `stale jobs 1` while branch code reports `stale running 1; stale queued 0`. Resolving the reporter/test contract requires a tested intentional decision. Do not cherry-pick its entire branch.

### Targeted salvage categories — candidate only

1. **Evaluate for reuse, do not automatically import:** `luna/worker_heartbeat.py`,
   `luna/maintenance_audit.py`, `luna/activity_timeline.py`,
   `scripts/luna_doctor.py`, and `luna/support_snapshot.py`. Each may help truthful
   worker/readiness reporting, but must be rechecked for privacy, freshness,
   duplicate code and valid schema against today's main. Existing `luna/attention_feed.py`
   and API status methods are authoritative unless a particular behavior is missing.
2. **Security-critical, requires separate review and OS evidence:**
   `luna/runner_executor.py`, `luna/runner_spec.py`,
   `luna/runner_activation.py`, `luna/runner_config.py`, `Containerfile.luna-test`,
   `luna/repair_orchestrator.py`, `luna/development_candidates.py`, and
   `luna/development_worker.py`. Never present unreviewed generated-code
   testing as a secure sandbox. The existing Linux runner and this branch's
   trusted baseline subprocess are different trust levels.
3. **Policies and review contracts, not deployed security services:**
   `owner_guard/intake_contract.py`, `luna/sensitive_intake.py`,
   `luna/sensitivity_policy.py`, and `luna/watchdog_events.py`.
   The owner's separate secure vault and independent watchdog do not exist merely
   because these interfaces were drafted.
4. **Avoid competing state stores/recovery paths without reconciliation:**
   `luna/backup.py`, `scripts/backup_luna.py`, `luna/readiness.py`,
   `luna/versioning.py`, and historical `VERSION`.
   Main already has `luna/database_backup.py`, `luna/launch_guard.py`,
   `luna/backup_schedule.py` and a centralized `luna/release.py`.
   Follow retention choice C: preserve all user data and backups.
5. **Historical collaboration and helper scaffolding:**
   `collaboration-feed/`, `luna/development_relay.py`,
   `scripts/watch_luna_activity.py`, `luna/model_autonomy.py`,
   and `luna/sprint.py` are not evidence of a continuously connected Codex run
   or real agency. Reuse only after an actual missing acceptance test is identified.
6. **Fixed/current elsewhere:** PR #2's false complete-syntax status now has a
   targeted regression in #34. PR #3 diagnostic command is a small separate
   follow-up; do not conflate it with real sandbox execution. PR #12/#13/#15
   are largely overlapped by main, but close only after checking net-new diffs.
   PR #28 financial planning remains unmerged and grants no spending rights.

## Hard blockers requiring actual hardware or owner decisions

1. **Only one authoritative private SQLite state** must be migrated from the
   actual existing Chromebook installation to the Mac, with WAL-aware consistent
   backup, encrypted protected transfer, integrity-checked restore, one active
   writer, and rollback. No copy of the text recovery archive substitutes for this.
2. **Live local inference on the Mac M4 mini**, owner-visible streaming/recovery,
   model quality and cost evidence. Existing tests use mocks; a model discovery
   probe is not a completed live conversation.
3. **Mac LaunchAgent, power/sleep recovery and restart** with actual logs,
   worker readiness and owner review of interrupted jobs.
4. **Contextual owner consent and automatic resume** for more than fixed
   approved goal recipes; no approval can broaden authority or imply release.
5. **Isolated model-generated-code repair and rollback** with trustworthy
   executor tests on the intended host; no untrusted code in the live database
   process.
6. **Authenticated and revocable mobile pairing**; current app is *localhost
   only*. Never expose it on LAN, internet, tunnels or reverse proxies as-is.
7. **Actual owner signoff** before merging or publishing a new release or final
   Flight Plan. Pojo.3.1.0 labels this coordination checkpoint, not a shipped app.

## Next engineering sequence

Review the CI-green stacked PRs (#34 → #35 → #36) as one candidate and
independently inspect security/consent. Then close the remaining real source
gaps by least-invasive tests, reconcile PR #1's high-value modules under
targeted review, and run the Mac/Chromebook acceptance steps when available.

No step in this document triggers provider calls, merges, software installs,
network exposure, or paid operations.
