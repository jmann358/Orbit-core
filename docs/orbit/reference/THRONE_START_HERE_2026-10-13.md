# POJO THRONE — START HERE / RESUME WITHOUT REWORK

**Owner's instruction to THRONE:** Read this complete handoff once, fetch the newest GitHub issue #52 comments and live source state, then **implement only confirmed remaining gaps**. Do not re-run a whole-project audit, re-ask settled architecture choices, reimport overlapping PRs or overwrite the already-working Mac installation. Section designs are prepared by HELM, **not yet implemented**.

**Prepared by HELM:** 2026-10-13. GitHub source review only; no GitHub mutation, deployment, Mac connection, private SQLite read, paid services, account or network changes. All 8 sections are DESIGN READY; 293 acceptance scenarios are **specified but not automatically passed**. The 15-test offline evidence assessor is separate synthetic reference, not a running Luna integration.

## 1. Read the currently reliable state, not a stale document

1. [Issue #52 latest handoff](https://github.com/jmann358/Orbit-core/issues/52#issuecomment-6133567244): exact installed Mac SHA reported as `560419de5f21102c9c9995de57dd4bb8890837f9`, one local model reply, completed health job and service-restart persistence; private pre-update snapshot; original Chromebook database preserved and stopped. The note's **later** owner amendment requires a free blackout companion while THRONE stays primary sole authoritative writer.
2. [Cumulative draft PR #58](https://github.com/jmann358/Orbit-core/pull/58): currently inspected as open/unmerged, `fix/throne-plan-and-worker-transactions`, head `560419de5f21102c9c9995de57dd4bb8890837f9`. Exact-head CI and Mac each reported 502 passed / 13 warnings. `main` still represents published `pojo.2`, **not** a new release.
3. `docs/FLIGHT_PLAN.md`, `docs/THRONE_STATUS.md`, `docs/ZERO_COST_CLOUD_READINESS.md` in this candidate contain historically stale source snapshots and/or sole-host/no-cloud wording. Prefer the newer owner issue #52 comment for amended requirement; update docs only under a reviewed source change. No cloud account exists and no second writer may be introduced.
4. Before editing, independently read local `git status`, installed commit, service state, protected backups, recent task result and Mac model health. No forced upgrade, restart, physical move, source rewrite or database copy merely because this document exists.

## 2. What HELM finished — no need to redesign

| Contract | Exact local file | Test matrix | Planned cases | Status |
|---|---|---|---:|---|
| 01 Mission approvals/lifecycle | `01_MISSION_APPROVAL_LIFECYCLE_CONTRACT.md` | `01_MISSION_APPROVAL_TEST_MATRIX.csv` | 28 | Design ready |
| 02 Independent proof | `02_RESULT_EVIDENCE_VERIFICATION_CONTRACT.md` | `02_RESULT_VERIFICATION_TEST_MATRIX.csv` | 44 | Design ready |
| 03 Memory/privacy/retention | `03_PRIVACY_MEMORY_RETENTION_CONTRACT.md` | `03_PRIVACY_MEMORY_TEST_MATRIX.csv` | 72 | Design ready |
| 04 Backups/uptime/recovery | `04_BACKUP_UPTIME_RECOVERY_CONTRACT.md` | `04_BACKUP_RECOVERY_TEST_MATRIX.csv` | 29 | Design ready |
| 05 Mobile authentication/access | `05_SECURE_MOBILE_ACCESS_CONTRACT.md` | `05_MOBILE_SECURITY_TEST_MATRIX.csv` | 31 | Design ready |
| 06 Cloud blackout companion | `06_CLOUD_BLACKOUT_COMPANION_CONTRACT.md` | `06_BLACKOUT_STANDBY_TEST_MATRIX.csv` | 27 | Design ready |
| 07 Safe isolated self-development | `07_SAFE_SELF_DEVELOPMENT_CONTRACT.md` | `07_SELF_DEVELOPMENT_TEST_MATRIX.csv` | 31 | Design ready |
| 08 Budget/specialists/financial/future UX | `08_RESOURCE_FINANCIAL_SPECIALISTS_CONTRACT.md` | `08_RESOURCES_FINANCE_TEST_MATRIX.csv` | 31 | Design ready |

Related materials included: `LEGACY_PR_DISPOSITION.md`; Sections 02/03 sanitized JSON examples; `REQUIREMENTS_CROSSWALK.csv`; `THRONE_ACTION_QUEUE.csv`; prior `POJO_HELM_FIRST_AUTONOMOUS_MISSION_2026-10-12.md`; the offline evidence assessor source and tests. `SECTION_LOCK_REGISTER.md` is the *status truth*. GitHub code remains unchanged by HELM.

## 3. Implementation order — one bounded package at a time

**P0-0 — establish precise state and backups.** Confirm SHA and cleanliness. Verify local chat, worker and immutable approved memory readback without risking source/migration. Make a new independent **encrypted** snapshot of newer Mac data and rehearse restore to disposable storage after separate owner target approval. Keep original Mac and Chromebook copies; do not auto-delete. Physical full reboot/home and soak require scheduled owner approval.

**P0-1 — close privacy before networking.** Implement Section 03 pre-egress data-class checks (historical snippets versus **current chat, approved memory and attachments**), agent context boundaries, active-memory correction and sensitive intake with synthetic data. Preserve Retention C and model independence. Security behavior must fail closed.

**P0-2 — make the first *real* autonomous mission.** Integrate Section 02 trusted verifier into existing receipts, with exact GitHub SHA/workflow and scoped health evidence; Section 01 version-bound inline approval, modification, truthful cancel/pause and active mission visibility. Replace hardcoded `development_plan` report with a **bounded evidence-based issue prioritizer**, not arbitrary new commands. Demonstrate: user requests project analysis → durable mission ID → Luna reads actual allowed evidence → selects one justified issue → produces reviewable recommendation → independent verified/inconclusive receipt survives browser closure and restart. Preserve worker-said-complete versus verified distinction. Do not add generated-code execution for this milestone.

**P0-3 — recoverability acceptance.** Verify home reboot/login, persistent jobs, failure and lease handling, low disk, broken local model and 24h normal-use soak; verify backup failure reporting and no second worker or writer. Do not pull power; disclose FileVault unlock dependency.

**P1-1 — phones.** Section 05 scoped device auth + private transport; auth not replaced by Host/Origin protections or overlay VPN; user approves provider/transport/pairing; test real iPhone and iPad with session revocation and racing approvals; Mac retains one writer.

**P1-2 — cloud blackout.** Section 06 staged **read-only sanitized status / separate owner inbox**, hard $0 cost gate, no live SQLite replication, no automatic takeover; first select supported free provider and obtain provider/data consent. Simulate split-brain/expired envelopes and rehearse explicit reconciliation on rejoin.

**P1-3 — isolated development.** Section 07 select owner-approved Mac VM/isolation and prove hostile code cannot read private Mac memory, network, secrets or host files. Only then execute **synthetic** candidate, bounded repair, independent trusted proof and reviewable diff. No automatic merge/install or self-authorized approval. **Legacy PR #1's `repair_orchestrator` defaults `owner_approved=True`; do not transplant as consent.**

**P2 — value and finish.** Section 08 enforce zero-cost pre-call budget, then one scoped read-only specialist and truthful finance opportunity ledger. Select a concrete lawful pilot only when owner reviews actual proposal/costs/external actions. Voice/personality/visual polish remain preserved features, not blockers for first autonomous mission.

## 4. Global stop/owner-approval boundaries

- Never merge/release `pojo.3`, install code, enable paid providers, create accounts, publish ports, pair devices, copy private data, alter money, run untrusted generated code or broaden permissions because of a handoff word or a green test.
- Owner authorizes sensitive changes **separately**, while routine bounded implementation on isolated branches can proceed as already permitted. Any cloud provider disclosure requires recipient, content class, purpose and retention scope, not blanket consent.
- A phone is not another Luna runtime. An old Chromebook backup is historical, not another writer. A free cloud inbox is not automatic failover of authority.
- For every task log requirement IDs, SHA, code changes, synthetic vs real tests, observed result, unresolved failures, necessary approval and rollback. Never claim that proposed acceptance cases were already executed.

## 5. What would justify reopening HELM design

Only a demonstrated implementation contradiction, new source vulnerability, failed acceptance, OS/provider support constraint, or a new owner requirement. Resolve a single conflict by amending that section with exact source evidence; don't re-audit the entire project.

## 6. First next action when Mac is available

**Read issue #52 newest comment and PR #58, inspect Mac installed SHA/status and backed-up private data without modifying anything.** If SHA is still the recorded installed `560419d`, use it as candidate; don't regress to `main` pojo.2. Report exactly one current P0 blocker from the work queue and start implementing that bounded package with existing tests and contracts. If backup of newer Mac private state isn't independently protected, close that safety issue before risky development.

### Copyable session instruction

> POJO THRONE. I am resuming from HELM's `THRONE_START_HERE_2026-10-13.md` and `SECTION_LOCK_REGISTER.md`. Read issue #52's newest comments, PR #58 and my Mac installed state. Treat Sections 01–08 as completed **design specifications**, not completed code. Preserve the installed baseline and private memory. Implement only the next verified gap, test it, record exact evidence and continue in dependency order. Do not redo earlier planning or merge old stacked PRs separately. Ask me only when a sensitive permission, physical action or real provider decision is genuinely required.
