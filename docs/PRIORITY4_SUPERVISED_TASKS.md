# Priority 4: supervised task operations

Priority 4 improves the **existing** Luna job worker rather than introducing a new,
unreviewed agent loop. The worker processes a fixed allowlist of local operations.
It has no permission to run arbitrary commands, install software, alter security
settings, merge pull requests, deploy code, or spend money.

## What is implemented

### Durable task lifecycle

SQLite persists each work item, attempt count, max attempts, retry eligibility,
result, and state, with an append-only **work_events** table for task transitions.
Older databases are migrated in place without losing messages, tasks, or notes.

States: `queued` → `running` → `completed` or `attention`. The only
automatic retry state is `retry_wait`. A job may also be `cancelled`
before execution. Each claim increments the attempt counter.

The **Approvals → Task inbox** displays current state, attempts, next retry
time, and an expandable history. No untrusted task title or detail becomes
executable code.

### Safe retry policy

Only temporary failures reported exactly as `GitHub unavailable` for the
allowlisted **github_status** read-only operation are retried unattended.
At most **two** additional attempts are allowed, after waits of **30 seconds**
and **120 seconds**. Successful calls, failing CI results, syntax errors,
internal task exceptions, and other failure categories are not retried
automatically.

After all attempts fail, the job enters `attention`. A deduplicated,
locally stored request is created for owner inspection. No contact with
ChatGPT, GitHub, or another external service is initiated by the escalation.
Other tasks stop after the initial failure. The owner can manually request
a new attempt for previously failed allowlisted low-risk kinds. Model-backed
workshop drafts cannot be replayed through this shortcut.

### Persistent pause switch

**Approvals → Supervised task worker → Pause new work** disables automatic
task scheduling and further job claims in the existing worker loop.
Existing running work is allowed to complete. Paused state is stored in
SQLite and remains effective after a server restart. **Resume approved work**
restores processing of queued items. Pausing does not delete any task.

This switch is distinct from **Overview → Pause independent work**, which
controls the existing Tier 1 autopilot schedule. Both remain available, and
pausing the task worker prevents any queued automatic task from starting.

### Auditing and recovery

An interrupted `running` job becomes `attention` on startup and is **never**
automatically replayed. A previously scheduled, explicitly retryable
`retry_wait` job may resume only after its delay and when the worker is on.
All manual retries, claims, cancellations, and completions are recorded.

The queue is capped at 50 pending/running/retry-waiting tasks for ordinary
job creation and autopilot scheduling. Routine deduplication treats
`retry_wait` as active, preventing overlapping copies of a scheduled check.

### API changes (localhost only)

- `GET /agent/worker` — persisted pause state and queue counts
- `POST /agent/worker` — `{"enabled": false}` pauses new work; true resumes
- `GET /agent/jobs/{id}/events` — read-only event history
- `POST /agent/jobs/{id}/retry` — explicitly request a new attempt for
  an attention-state, low-risk, allowlisted task
- Existing `GET /agent/jobs` includes `attempt_count`,
  `max_attempts`, and `next_attempt_at`.
- Existing `POST /agent/jobs/{id}/cancel` now accepts an unstarted
  `retry_wait` task as well as a queued task.

No new external endpoints, authentication exceptions, dependencies,
or permissions have been added.

## Operational boundaries

This does **not** turn Luna into a self-modifying or general-purpose
autonomous software engineer. Source patches remain review-only and
deployment still requires separate explicit owner approval.

The worker runs only while the ORBIT server process is active.
This is not a separate always-on daemon. A single local worker process
is expected: do not run multiple independent Uvicorn workers or
publicly expose the unauthenticated dashboard. The SQLite DB is the
durable source of task state, not the browser tab.

The older baseline testing endpoint still executes trusted tests in a
temporary copy, not a sandbox for generated code. The Linux sandbox
runner from Priority 2 remains manual and explicitly approved.

The automated regressions verify the database migration, event log,
three-attempt limit, delay timing, retry deduplication, restart safety,
manual replay permissions, persistent pause, API routes, and queue
capacity. Runtime testing on the user's own Chromebook is separate.

## After merge

On the Chromebook, from `~/Orbit-core`, run `git pull --ff-only origin main`
and restart the locally running Luna server normally to load the new
code. On its **Approvals** tab, inspect the worker controls and queue.
No package installation is required.

If any task is stuck in `attention`, view its history and choose whether
to retry or investigate; do not assume a green GitHub check establishes
that the running installation has been updated.
