# POJO HELM → THRONE | Section 04: Backup, Uptime, Recovery

**Status: DESIGN READY / implementation and physical-host acceptance PENDING.** Prepared 2026-10-13 from inspected PR #58 head `560419de5f21102c9c9995de57dd4bb8890837f9`. This document is not permission to reboot THRONE, alter live memory, choose external storage, buy hardware, or activate services. Use `04_BACKUP_RECOVERY_TEST_MATRIX.csv` as the executable acceptance queue, not as evidence of tests having run.

## 1. Purpose, known working foundation, specific gaps

The aim is a Mac-hosted Luna which continues safely after process restarts, normal household interruptions and partial failures, and has demonstrably restorable recent data. Do not equate service registration with a live healthy AI model, a verified backup with a restore, or an ordinary service restart with recovery from a power outage.

Existing source to **reuse**:
- [`luna/database_backup.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/database_backup.py): SQLite online backup into new local paths, integrity inspection and restrictive file modes. Source/backup fingerprints are **private**; don't post them.
- [`luna/backup_schedule.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/backup_schedule.py): one-day eligibility check for valid recent `luna-before-self-build-*.sqlite` snapshots. A helper's existence is not proof the schedule runs in deployed conditions.
- [`luna/restore_rehearsal.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/restore_rehearsal.py): temporary restore and structural comparison; add semantic checks for approvals, receipts and sessions using disposable fixtures.
- [`scripts/luna_mac_service.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/scripts/luna_mac_service.py): LaunchAgent login/start/restart with `KeepAlive`, **not pre-login startup**.
- [PR #58](https://github.com/jmann358/Orbit-core/pull/58) and [latest verified handoff](https://github.com/jmann358/Orbit-core/issues/52#issuecomment-6133567244): real model reply, controlled service restart persistence, one worker, loopback binding and previous private snapshot reported; physical home reboot/soak and independent post-cutover backup remain unverified.

**Known risk:** old Chromebook snapshot protects only older state; no proof yet of recoverable independent backup of newer Mac records. Never overwrite or delete the Chromebook original or backup automatically.

## 2. Mandatory operating contract

### Data and writer consistency
1. THRONE owns the **only authoritative SQLite writer**. When restoring, the service/worker is stopped and fenced *before* any file replacement. Cloud companion and old Chromebook cannot write to this database; no unsupported network-filesystem SQLite multiwriter arrangement.
2. Snapshot active SQLite with its **online backup API**, not an ordinary copy of a live `.db` without its WAL. Snapshot location must be new, private, non-symlink, outside source control, and protected by directory and file modes. Log metadata only; never log rows, secrets, full DB paths where sensitive, or content-derived hashes publicly.
3. Take an initial post-cutover independent snapshot before treating THRONE as disaster-ready; thereafter proposed target: **at least daily** while in operation and **before any risky update/migration**. If a backup is missed, alert; do not claim up-to-date recovery.
4. Restore rehearsal must prove structure **and** retained synthetic business invariants: sessions, approved vs pending memory, proposal revisions, audit history, job/approval state, and receipt associations. `integrity_check='ok'` alone cannot prove application-level continuity. Preserve rollback source and a documented operator recovery path.
5. Record snapshot creation/verification time, independent storage location class (not private path), version/schema, restore drill result, last failure, age and age threshold. Recommend **24-hour recovery point objective** as an initial *target*, not a guarantee. Measure actual recovery time on THRONE before publishing any recovery-time promise.
6. Never auto-delete existing history or backups under Retention C. If storage low, pause risky writes/new jobs and ask owner for a storage/retention decision, not silent pruning.

### Service recovery and jobs
7. Treat four states separately: host off; Mac booted but encrypted volume locked/user not logged in; Luna process alive; Luna model+worker independently healthy. Show owner exactly which state is known and what remains unknown.
8. During normal login-based recovery, verify model response, database readback, worker heartbeat and at least one saved result. If Ollama, disk, network or worker unavailable, degrade honestly and preserve chat/mission state.
9. Crash recovery and `lease_until` logic must not double-execute consequential effects. An uncertain outcome goes to `attention`, not automatic replay. Owner-approved work is never implicitly upgraded by reboot.
10. Test lock/sleep and browser closure without forcing physical power removal. Any actual full reboot should occur at a separately agreed owner time, and should disclose the FileVault login/unlock dependency.
11. A prolonged normal-use soak should observe resource health and the newest durable record across a 24-hour *proposed* observation window. Detect duplicate workers, unstable loops, runaway CPU/RAM, growing logs, missing snapshots and abandoned jobs. Failures are recorded, not silently 'passed'.
12. Restore may be destructive only after explicit owner review of exact source and destination, independent validated snapshot, stop/fence, a dry run, and a rollback plan. Prefer **disposable test DB** for initial acceptance; no overwriting live records during ordinary tests.

### Failure and disaster response
- Database corrupt, unreadable or permission-denied: stop new memory and mission writes, mark degraded, preserve files; do not initialize empty state over the original.
- Disk full / snapshot failure: report backup age and actionable storage warning; preserve existing copies; fail closed before unsafe update.
- Internet down: local inference may continue if operational; GitHub/remote actions wait without falsely claiming completed work. Never change privacy or budget gates to recover a heartbeat.
- Mac stolen/destroyed: recover only from independently protected encrypted medium; no imaginary cloud replica. If no independent snapshot, explicitly report the gap.
- Post-restore: verify authority epoch and pending/uncertain operations before re-enabling worker; stale approvals and prior effects must not replay.

## 3. Concrete THRONE implementation queue

**R04-A (P0, synthetic):** Reconcile `backup_schedule`, `database_backup`, `restore_rehearsal` and real app startup call sites; add deterministic daily/pre-change backup job with private status ledger, failure alerts and no automatic deletion. Include WAL-in-flight fixture, corrupted backup, symlink, disk full, collision, expired snapshot and failed restore. Reuse existing helpers; do not invent a second backup system.

**R04-B (P0, synthetic):** Add restore semantic manifest and fenced reactivation. Distinguish restored checked state from resumed action. Require exact source revision/schema and a disposable restore drill before live operations.

**R04-C (P0, THRONE):** Owner chooses independent encrypted target. Make one snapshot of newer Mac data and prove a **separate-medium** disposable restore. Preserve source/backups until accepted; do not upload into ChatGPT, GitHub or cloud standby.

**R04-D (P1, THRONE):** At owner-chosen time conduct transport/home-network boot → owner unlock/login → service/model/worker/receipt checks, controlled provider loss/recovery, then 24-hour normal-use soak; capture sanitized evidence only.

## 4. Exit, evidence and reopen criteria

**Design ready now:** dependencies, behavior, safety boundaries and tests below. **Implementation closed only when:** source tests pass at exact revision, off-host backup/restore passes, post-login recovery and soak are observed, failure states are truthful, and owner accepts explicit downtime/retention limits. Every result needs code SHA, fixture/host, observed time, proof artifact without private data, reviewer and rollback procedure.

**Reopen design only on** new security finding, new owner requirement, OS capability change, conflict uncovered by actual restore/soak, or demonstrable testability gap. Do not reopen simply because THRONE is ready for implementation.

Mapped master gates: T03/T15/T20/T21/T24/T32, V11–V16, V18. Dependencies: 03 privacy, 01 mission state, 02 receipts, installed-source comparison. Future 06 cloud fencing must not change sole-writer rule.
