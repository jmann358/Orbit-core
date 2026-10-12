> **Pojo.3.1.0 flight update (2026-10-12; unmerged draft):** P1 trusted test environment hygiene, atomic backlog dispatch, deterministic SQLite connection closing, real Uvicorn chat-to-task receipts, two ordered approved goal steps, inline approval controls and worker heartbeat observations are now covered by draft-branch CI. Historical "Planned" status cells below are not authoritative for those specific subfeatures; consult [candidate acceptance evidence](POJO_3_1_0_ACCEPTANCE_EVIDENCE.md). Platform-dependent Mac live model, verified database migration, secure generated-code test/repair/rollback, mobile authentication and broad autonomous planning remain blocked or unverified. `main` remains pojo.2; do not count this as a published release.

> **Integration update (2026-10-11):** This roadmap table records an earlier audit baseline; its status cells are not a complete inventory of the merged release. See [master-plan reconciliation](MASTER_PLAN_RECONCILIATION.md) for the original architecture matched to current code and outstanding live-host acceptance tests. PRs #16–#19 merged a bounded developer worker, draft-PR handoff, one-command local model startup and a private memory backup guard. Live model, Mac/iPhone and unattended uptime are not yet verified.

# Development roadmap

The delivery target is a usable Luna conversation interface with persistent,
owner-reviewed memory. Each milestone has observable exit criteria. A feature
is complete only when its evidence is recorded in `PROGRESS.md` at an exact
revision. This roadmap does not authorize merges, spending, or deployment.

| Order | Deliverable | Exit criteria | Current state |
| --- | --- | --- | --- |
| 1 — P0 | Reliable configured-model replies | Null, empty, malformed, non-text, and invalid UTF-8 replies cannot crash chat or enter memory/history as valid answers. Invalid endpoint syntax produces a safe readable failure without a request. A subsequent good reply succeeds and saved history remains available. Endpoint restrictions remain enforced. | Implemented with mocked-provider regression evidence: 37 new cases, 219 full-suite passes. Live model verification remains pending. |
| 2 — P1 | Usable conversation and memory flow | A browser can start/reopen a session, send/reload messages, switch sessions during a delayed reply, and submit once while pending. Approved memory reaches later model context; pending/rejected memory does not. Verify persistence across process restart with disposable SQLite. | Partial: mocked-provider memory and process-restart persistence verified; browser and pending-send checks remain. |
| 3 — P1 | Explicit model state and errors | Local setup/status identifies missing configuration and distinguishes provider failures from assistant content. Every drafting/planning caller handles typed outcomes. Provider adapters share a response contract with mocked contract tests and an approved live/local smoke check when available. | Planned. |
| 4 — P1 | Repeatable local operation | Supported Python/test setup is documented and checked. Database connections close deterministically; migrations preserve data; launch backup respects configured paths and validates integrity; restore rehearsal succeeds on disposable data. Resolve README case collision. | Planned; coordinate launcher PR #12. |
| 5 — P1 | Trustworthy task operations | Backlog dispatch is atomic under competing ticks and crash points. Lifespan tests demonstrate worker startup, pause, recovery, shutdown, and failure reporting; healthy basic checks do not imply product completion. | Planned. |
| 6 — P2 | Mac M4 home-base readiness | Case-safe checkout, local model configuration, backup/restore, restart supervision, and everyday chat/memory flow are tested on the intended Mac. Resource requirements and remaining limits are measured. | Blocked on available Mac hardware and owner install context. |
| 7 — P2 | Authenticated device access | Owner approves a concrete pairing/authentication/transport/revocation/retention design. Implement and test it on a focused branch, then verify iPhone chat and reconnect behavior before approving network exposure. | Design pending; network exposure unauthorized. |
| 8 — Later | Broader assistant capabilities | Approved provider routing/accounting, isolated model agents, connected skills, proactive delivery, and voice each have scoped permissions, bounded resource use, user flows, and measurable acceptance evidence. | Deferred until core product reliability. |

## First delivered change

The existing `luna/core.py` adapter now validates provider text and URL
configuration. `tests/test_model_reliability.py` verifies graceful failures,
subsequent recovery, approved-memory context, provider switching, and persisted
history reopened by a fresh Python interpreter. Full-suite results and limits
are in `PROGRESS.md`. Security and access are unchanged.

Next, address pending-send/session-switch behavior in the existing interface
and obtain interactive browser evidence. Follow with explicit model outcomes
so drafting callers cannot mistake configuration notices for valid proposals.

## Coordination and maintenance

Review open PRs #12, #3, #2, and #1 before implementing overlapping launcher,
diagnostic, screening, or sprint work. Prefer repairing the existing paths over
parallel replacements. Reorder this roadmap when measured user-facing failures
warrant it, and record the reason in `DECISIONS.md`.

Each progress update should link the changed sources, test command/result,
commit or PR, remaining blockers, and the next acceptance check. Avoid labeling
static catalogs, fixed specialist labels, mocked provider responses, or passing
CI as completed integrations, independent agents, or verified deployment.
