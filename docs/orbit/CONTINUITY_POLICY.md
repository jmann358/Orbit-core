# ORBIT continuity governance v1 — minimal and stable

## Immutable decisions vs moving pointer

The **protocol and schema** should change only via deliberate reviewed migrations. The **state** naturally updates after actual work. These are not contradictory: preserving history *requires* updating the current pointer, not rewriting old evidence. Git commit history plus the embedded SHA-256-linked events make inadvertent revisions visible but are not cryptographic authentication or secure against an actor who can rewrite history; repository access controls and reviews remain essential.

- Never mark an unverified feature complete on design alone, synthetic CI alone, or worker self-report.
- Preserve legacy PR sources: prefer a single cumulative integration candidate, avoid parallel edits on THRONE's active branch, and review before merge.
- Each checkpoint event currently records: actor, work ID, new status, note, evidence URL, timestamp, revision and previous event hash. The exact tested revision, prior state, blockers and successor must be read from linked evidence/Git history and current state; they are **not** all stored in the event itself. Do not infer their verification from an event. Never include credentials, personal data, private paths, raw DB hashes or customer information.
- Checkpoint local file via `python scripts/orbit_resume.py --checkpoint --expect-revision N --work-id P0-0 --status review --note '...' --evidence 'https://...'`. Then a separate authorized Git commit/PR is needed; **local changes are not automatically published**.
- GitHub concurrent edits need a compare-before-push/checkpoint discipline. The script's `.lock` protects only the local checkout. Two devices cannot both be writers to THRONE's personal database.
- `completed` requires an evidence-bearing HTTPS reference and verified dependencies. Human review and actual acceptance separate from automated status.
- If a checkpoint disagrees with live Mac/remote PR evidence, label it stale, do not quietly edit historical events; append a correction describing the source.
- Ideas: append one distinct ID line. Do not store private relationship, personal health, tokens, account balances, credentials, customer information, or chat transcripts in GitHub. Ask before promoting scope-changing ideas into committed active work.
- When the user says 'pick up where we left off', always **fetch** GitHub and read this state; do not fabricate access or start with a new intake questionnaire.
- If the repository is unavailable, show last known snapshot labeled stale and request connection/link; do not assume unseen updates.

## Source of truth hierarchy
1. Owner's **current** explicit instructions and executable authority/permissions.
2. Live, independently checked current host/source/CI state (when accessible), supported by evidence.
3. `docs/orbit/STATE.json` priority, plus dated issue #52 evidence for operational history.
4. These versioned contracts/tests for what to build.
5. Old tickets and conversation recollections for historical context only.

Codewords and memory summaries are pointers, not an authorization to access or execute anything.

## Minimal verification and evolving task queue

Run `python scripts/orbit_resume.py --json` and `python scripts/orbit_resume.py --audit` at the start of a new development session. The audit checks the pinned 30 reference file hashes, 333 scenario IDs, and outcome bookkeeping; it does **not** perform product tests or trust linked evidence automatically. The original `reference/THRONE_ACTION_QUEUE.csv` is archival design input; use `STATE.json` for the current, corrected 13-work-item queue. Distinguish CI-in-progress from CI-green, and never assume the Mac is online. After an intentional new acceptance case or section, update the manifest, counts and validator together in one reviewed change instead of treating hard-coded version-1 totals as eternal.
