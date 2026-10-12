> **THRONE status supersedes older status claims below.** Read [THRONE_STATUS.md](THRONE_STATUS.md), [FLIGHT_PLAN.md](FLIGHT_PLAN.md) and [PLAN_RECONCILIATION.md](PLAN_RECONCILIATION.md) first. The dated entries below are retained evidence, not a live task list.

# Pojo.3.1.0 — first-flight stability integration (review only)

**Status:** draft, not merged, deployed, installed or owner-published.
**Application version on main:** `pojo.2`. Pojo.3.1.0 is an owner
coordination checkpoint, not a version bump or a claim of completed autonomy.

## Source of truth and tracked repairs

Starting revision: `baf96abff8105b89e7b4c924ff03921f084923b5`.

- **F-06 / PR #32:** limit trusted baseline test subprocess environment,
  direct all test DB and temp state to a disposable workspace, and report
  explicitly that a directory copy does NOT provide OS sandbox isolation.
  Model-generated code must never execute in this routine.
- **F-07 / PR #33:** share job insertion logic and make
  backlog selection/budget, work-item insertion, audit event and source task
  linkage one `BEGIN IMMEDIATE` transaction. Crash-injection and
  competing-worker tests prove rollback and at-most-once queueing.
- **F-09 / legacy PR #2:** refuse to report full syntax screening for a
  proposal with more than 12 discovered Python blocks. Preserve the
  reviewer-visible distinction between checked, truncated and valid blocks.

Every original fix remains reviewable in its source PR; this integration
cherry-picks only the necessary current-main-compatible behavior. Do not
merge PR #1 wholesale: it is historically conflicted and has unresolved CI.

## Proof required before considering merge

CI must pass the complete trusted Python 3.11 and 3.13 suites at the final
integration head. Check GitHub Actions on this PR, including syntax,
case-insensitive Mac paths, and the new targeted tests.

Additionally, reviewers must verify:
- No owner/model/GitHub credentials or actual SQLite database reach trusted
  test subprocesses via inherited environment.
- The test runner is still NOT a sandbox suitable for model-authored code.
- A crash in dispatch cannot commit a work item without its backlog link.
- Concurrency cannot allocate the same backlog task twice.
- A 13th unexamined draft block cannot be misreported as fully screened.

## Still unverified and release-blocking

Passing CI is not evidence that Luna is self-sufficient. The next milestones
remain one real host goal/task/worker/result receipt, live local model/helper
inference, explicit and resumable inline approvals, safe generated-code
execution/rollback, verified Mac service and SQLite migration, and authenticated
iPhone/iPad access. These require separate implementation and host evidence.

`docs/FLIGHT_PLAN.md` is **not** created by this integration. The user's
reviewed Flight Plan remains subject to its separate final approval.

## Owner Mac: safe read-only first check

Once at the Mac (without installing, connecting accounts or publishing), run:

```bash
printf 'Mac chip: '; uname -m
printf 'macOS: '; sw_vers -productVersion
printf 'Python: '; command -v python3 || true
if [ -d "$HOME/Orbit-core/.git" ]; then
  cd "$HOME/Orbit-core" || exit 1
  git status --short
  git rev-parse --short HEAD
  python3 scripts/luna_one_time_setup.py --check
else
  echo "Orbit-core is not checked out on this Mac."
fi
```

Do not paste personal database contents, API keys, tokens or passwords into
review threads or chat. Do not replace the authoritative Chromebook database
or launch a second independent persistent Luna until migration/recovery is
planned and checked. Mac setup/install/deploy and PR merging need separate
owner authority under `DEVELOPMENT_POLICY.md`.
