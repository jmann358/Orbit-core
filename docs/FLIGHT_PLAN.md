# Luna / ORBIT — consolidated staged completion plan

October 12, 2026 · Reconciled baseline 2.1 · Development authorized; sensitive gates remain

The owner requested reconciliation of old and new plans, retirement of obsolete station work, and progress through the recommended sequence until a genuine decision boundary. This baseline combines recovered historical requirements, GitHub evidence and verified THRONE setup. It authorizes no new spending, access, automatic code application, merge or release. See PLAN_RECONCILIATION.md, ACCEPTANCE_REGISTER.md and THRONE_STATUS.md. Original unavailable attachments remain a documented provenance limit, not silently discarded requirements.

## Consolidated full goal

Build Luna into a dependable, persistent, increasingly self-sufficient assistant and coordinator of ORBIT, hosted solely on THRONE, the Mac M4 mini. Luna should understand and remember approved context, initiate useful work, plan and complete authorized tasks, coordinate scoped specialists, verify and present real results, and improve through isolated testing and controlled releases. The owner should have full, secure access from the Mac, iPhone and iPad, with simple contextual approvals for consequential actions. Luna should create measurable personal, creative, technical and eventually financial value while preserving privacy, owner authority, recoverability and efficient resource use.

“Self-sufficient” means independently completing an approved class of work and escalating a specific exception. It does not mean unlimited permissions, guaranteed earnings, bypassing the login screen, or perfect reliability. ORBIT is the infrastructure; Luna is the central assistant. A responsive dashboard is only one part of completion.

## Settled requirements carried forward

- THRONE is the sole active host and authoritative database writer. Other devices are interfaces, not duplicate Luna installations. The Chromebook original and backup remain protected historical copies.
- The latest sole-host instruction supersedes older hybrid/cloud-hosting and multi-station execution plans. Optional outside model providers remain a possible separately approved integration, not a second Luna host or a current requirement.
- Financial productivity is a long-term success priority, followed by autonomous productivity, improvement, and personality/companionship. Dependency order still puts reliable execution before financial authority.
- Routine authorized work should proceed without repeated prompts. Scope changes, sensitive access, spending, live application, and releases remain controlled by the owner. Success does not grant new permissions.
- Personal memory requires approval and stays separate from technical/shared operational knowledge. Preserve existing history and backups; no automatic deletion until a retention policy is approved.
- Luna may disagree respectfully, express uncertainty, initiate useful conversations, and maintain a recognizable identity independent of the underlying model.
- Use existing queues, goals, approvals, receipts, memory and development modules before introducing replacements. Keep full audit trails with concise expandable summaries.
- $0 discretionary spending initially. No hidden paid retries, provider escalation, account creation, purchases, customer outreach or financial transactions.
- Keep the sequential `pojo.N` release convention. Planning approval, source review, merge, installation and release are distinct events.
- Preserve the larger vision: specialists, research/operations/creative work, integrations, notifications, financial intelligence, voice and the expressive ghost-girl identity. Function and reliability lead appearance.

## What is actually established

| Area | Evidence as of this review | What that evidence does not prove |
| --- | --- | --- |
| Published source | `main` is `baf96abff8105b89e7b4c924ff03921f084923b5`, label pojo.2 | No pojo.3 release; GitHub Releases API returned no release objects |
| Latest remote candidate | Draft #57 `fe9ef11c1de76d3f5c6aa9d2905c0c3feefa461b`, stacked on #56/#54; two latest exact-head workflow runs succeeded | Not merged; green CI is limited to its test scenarios |
| Installed Mac source | Local `ee067a390914c03bfc189bb8dfedf0f7bb59061e`, based on #57, with Mac test/path fixes; 492 tests passed, 13 warnings | This local commit is not yet preserved in a remote review branch |
| Local model and tasks | Genuine local chat reply, completed health-check job 27, saved result and chat surviving service restart | No complete autonomous development loop; one automatic draft reported model/validation failure |
| Memory transfer | Encrypted transfer, integrity/schema/count verification, restoration and sole-writer cutover completed | No ongoing independent off-device backup of new Mac changes or disaster recovery drill established |
| Powered operation | Login startup, process recovery, sleep disabled and restart-after-power-loss settings verified | Full reboot/home-network/long-duration acceptance remains; FileVault login is required after boot |
| Security | Loopback listeners, local origin protections, obvious-sensitive-input screening, private storage; transfer port closed | No phone authentication/pairing, comprehensive privacy classifier, isolated vault or Mac generated-code sandbox |
| Product foundations | Persistent chat, memory review, fixed task recipes, contextual fixed-goal approval card, readable receipts, bounded draft worker | No general-purpose planner, independent specialist runtimes, live connectors, or automatic safe promotion/rollback |

## Staged delivery

Use these stages as dependency gates, not calendar promises. Size is relative: S = focused work package, M = several coordinated packages, L = substantial subsystem requiring separate design and review. Every implementation package needs a source revision, requirement ID, owner, observable test, rollback method and evidence link before it is called complete.

### Stage 0 — establish one durable project record (S)

**Outcome:** future sessions continue without paying to rediscover the project.

Reconcile this plan with the original master blueprint, Flight Plan T01–T34, ATLAS review, financial directive and THRONE receipts. Preserve all requirements in one register. Review the installed local commit against fresh main and #57. Prepare one coherent integration diff and identify which of the 31 open PRs are superseded, independent or still valuable. Do not merge a stack repeatedly. Recover useful PR #1 work through a feature-by-feature provenance table; filenames alone are insufficient. Keep #28 financial work and #41 audit requirements visible.

Record the new Mac evidence in a sanitized proposed update to issue #52; it still contains obsolete pre-transfer status. Preserve the local Mac changes remotely only through a separately authorized publication. Align roadmap, decision log and future `docs/FLIGHT_PLAN.md` after owner approval. Review the deferred Node/Actions trust-pin upgrade separately; do not silently change the trusted launcher pin.

**Exit:** one agreed goal, full requirement register, dependency sequence, source/PR disposition, evidence rules and explicit exclusions. Missing original attachments are resolved or explicitly accepted as unavailable. Owner approves the planning baseline and separately chooses whether to publish it.

### Stage 1 — dependable permanent home (M)

**Outcome:** Luna reliably resumes on THRONE after normal household interruptions.

After the move, verify shutdown → transport → boot → login → service startup → actual reply → existing history/result. Test browser closure, screen lock, model absence, worker crash, interrupted jobs, Internet loss, low storage and backup failure using controlled tests. Do not pull power to simulate a blackout. Complete a proposed 24-hour normal-use soak before calling the home installation stable; extend only if failures warrant it.

Document login-required blackout recovery. Evaluate an optional UPS only if the owner wants protection from abrupt loss; no purchase is implied. Prove periodic WAL-consistent backup, failure alerts and restore into a disposable database. Propose owner-controlled encrypted backup on a separate medium and test restoration before relying on it. A retained Chromebook snapshot is valuable but cannot protect later Mac changes.

**Exit:** reboot/login and overnight operation observed; no duplicate execution or lost completed work; measured disk/model/worker behavior; recoverable recent backup; clear owner recovery instructions. Dependencies: Stage 0 baseline; backup destination approval before copying private data.

### Stage 2 — dependable conversation, memory and identity (M)

**Outcome:** Luna remembers the right things and communicates reliably across sessions.

Test real browser send/reload/reconnect, delayed replies, switching sessions during a reply, cancellation, failure/retry and duplicate submissions. Distinguish configured model, successful recent inference, unavailable provider and slow model. Measure actual response quality and warm/cold latency against agreed example tasks before selecting another model.

Implement or complete source-linked cross-session retrieval, conflict/correction handling, personal-versus-technical memory access, summaries with provenance, owner export/deletion flows, context limits and model-switch continuity. Preserve history by default. Keep pending/rejected personal memory out of approved-memory retrieval and define separately how ordinary chat history may be used. A model change must not silently transmit history to a new provider.

Keep Luna's identity/preferences stable, allow respectful disagreement, handle interruptions, and expose uncertainty. Validate sensitive intake without claiming that heuristic screening catches everything.

**Exit:** repeatable owner examples demonstrate recall, correction, privacy separation, restart persistence and failure recovery with no session crossover. Dependencies: Stage 1 storage/recovery; fixtures must be synthetic.

### Stage 3 — useful autonomous missions with clear approvals (L)

**Outcome:** give Luna an outcome, then inspect a finished result without managing every step.

Extend the existing fixed recipe system into a bounded mission planner with tool eligibility, dependencies, checkpoints, evidence requirements and limited replanning. Keep immutable approval scope; a changed consequential action requires a new revision. One persistent mission card should answer what Luna is doing, what she needs, what happened and where the result is.

Support approve, reject, replacement-plan modification, pause, safe cancel, resume, expiry and revocation; validate on the server at execution. Persist approval → job claim → effect → verification separately. Reconcile uncertain external outcomes instead of blindly replaying them. Preserve per-category budgets and existing tighter retry limits: ordinary work no more than two retries; developer validation currently has one extra attempt and two daily model attempts. Paid/uncertain-side-effect work must never inherit a generic automatic retry.

Add deduplicated useful triggers, truthful idle state, attention limits and a morning summary. Resolve the existing automatic draft failure without widening permissions or masking invalid output. Validate one real bounded multi-step mission, one mid-mission approval, one failure and one restart recovery. Choose initial fixtures from existing project-health, repository review and planning capabilities rather than inventing connectors.

**Exit:** Luna completes a meaningful authorized mission after the browser closes, continues after necessary approval, stops correctly, and presents independently checked evidence. Dependencies: Stages 1–2. No generated-code execution yet.

### Stage 4 — secure full iPhone/iPad access (L)

**Outcome:** the same Luna and same memory are available from the owner's devices at home and away.

Prepare an explicit owner-authentication, encrypted transport, pairing, device/session expiry, revocation, CSRF/origin defense and credential-storage design. Recommend private authenticated connectivity with a single THRONE backend; select the actual transport after assessing requirements and current supported options. A private network alone is not a substitute for application authorization. No unauthenticated port forwarding.

Use the existing web interface, adapted for phone/tablet controls, readable receipts, persistent task panel, keyboard/screen-reader support, reduced motion and meaningful loading/error states. Test conflicting approvals, revoked/lost device, reconnection, offline state, locked Mac and unavailable host. Queueing offline commands must not imply execution or preserve expired authority.

**Exit:** actual iPhone and iPad can chat, inspect results and approve only their current permitted actions; revoked sessions fail; Mac remains sole writer. Dependencies: reliable Stages 1–3 and owner approval of access/transport design. Design may proceed during Stage 3.

### Stage 5 — safe self-development and controlled updates (L)

**Outcome:** Luna prepares a useful improvement, tests it safely, repairs within limits and submits verifiable work for review.

Recover relevant runner/repair/security work from PR #1 only after semantic review. The present runner explicitly requires Linux bubblewrap and is not a verified Mac executor. Recommend a disposable isolated environment hosted on THRONE, with no owner data, credentials, host filesystem or outbound network by default. Select and approve the actual implementation before installing it; ordinary temporary folders, virtual environments and trusted baseline tests are insufficient isolation.

Bind every test to exact source and proposal fingerprints. Prove malicious candidate code cannot read memory/secrets, reach network/host sockets, persist, or evade CPU/time/storage/output limits. Then connect draft → isolated test → bounded repair → independent review → draft PR/local review. Keep sensitive files outside autonomous edit scope. Implement checkpoint, atomic promotion, schema compatibility, rollback and post-install checks before considering any narrowly delegated live application.

**Exit:** one real local-model improvement completes the full isolated cycle, a hostile candidate is contained, a broken update rolls back in rehearsal, and unauthorized merge/deploy attempts fail. Dependencies: Stage 1 recovery, Stage 3 mission/evidence system, explicit isolation-install approval. Phone access is useful but not a technical prerequisite.

### Stage 6 — specialized agents, useful integrations and resource control (L)

**Outcome:** Luna delegates real work without runaway cost or broad data sharing.

Start with one scoped specialist and one useful integration; expand only when a measured task needs it. Existing specialist labels/handoff envelopes are foundations, not independent agents. Add isolated identities, permission and context boundaries, cancellation, duplicate suppression, conflict handling and accountable handoff results. Scale sequentially on the 16 GB Mac before considering concurrency. Do not run dozens of loaded models simply because the architecture permits dozens of roles.

Select the first connector from actual owner needs: repository work, calendar, mail or files. Each needs explicit scopes, credential lifecycle, revocation, error/retry behavior and end-to-end tests. Separate read-only, drafting and sending/writing permissions. Add notifications with approved delivery channels, quiet hours and meaningful-change filters.

Add resource routing based on successful outcomes: deterministic tools/cache first, suitable local inference next, outside providers only with explicit access and cost approval. Usage counters must show unknown values honestly. If paid providers are ever enabled, require pre-call reservation, hard ceilings, concurrency-safe accounting, denial of unknown cost and reconciliation with actual billing. Current call-count caps are not dollar caps.

**Exit:** one meaningful delegated integrated workflow with traceable results, enforced data scopes and measured resource cost; revoked access and exhausted budgets fail closed. Dependencies: Stages 2–3; Stage 4 for remote notification UX; Stage 5 isolation boundaries where agents execute code.

### Stage 7 — financial intelligence and measured economic value (M/L)

**Outcome:** Luna helps identify and deliver legitimate value with transparent costs and owner-controlled money.

Reconcile PR #28 into the current architecture; it is only a read-only planning foundation. Implement persistent opportunity evidence, estimates versus actuals, expenses/revenue ledger, profitability, resource costs and audit history. Preserve the directive's live dashboard, weekly summary, monthly review and meaningful alerts.

Begin with research and one proposed low-cost pilot. Business/product, acquisition channel, payment method, reserve formula, loss caps, reinvestment and distribution rules remain genuinely unresolved. Decide them when the concrete pilot is reviewable. Require owner approval of initial samples and external delivery; retain owner-controlled accounts, purchases, contracts, payouts and filings. Do not assume coding permission authorizes customer contact.

**Exit:** a completed approved pilot with evidence of delivery and actual cost/outcome, or a documented stop decision; no invented income or guaranteed profit. Dependencies: Stages 3 and 6 for execution; research can begin earlier within existing permissions.

### Stage 8 — voice, expressive identity and long-term product finish (M/L)

**Outcome:** a polished everyday companion and control room that remains reliable.

Develop optional push-to-talk first, then approved speech output and interruption handling. Keep recording/retention/provider choices explicit. Provide text fallback, accessibility, reduced motion, stable ghost-girl identity and owner-selected themes/voices. Assess animation quality and CPU use on the actual Mac and mobile clients. Avoid always-listening behavior by default.

Complete usability review, documentation, backup/export portability, upgrade rehearsal and security review across all delivered capabilities. Demonstrate representative research, operations, creative, development and optional financial tasks. Publish only the owner-approved release and associated evidence; do not call future extension ideas release blockers.

**Exit:** owner accepts the representative scenarios and remaining limitations; every in-scope requirement has evidence or an explicitly approved deferral. Dependencies: stable core; voice prototypes can be isolated earlier if they do not delay critical work.

## Named loose ends that must not disappear

1. **SQLite review finding resolved in candidate source:** reproduced partial writes surviving an exception with synthetic data. Use deferred transactions for ordinary DML and start explicit immediate transactions before developer setup writes. Successful commits, implicit/explicit rollback and atomic enqueue now have regression coverage. This repair is not yet installed; critical consent paths already had explicit transactions, so no consent breach was established.
2. **Observed failed automatic draft:** preserved. A disposable replay failed proposal validation twice; the new local schema-constrained output reached review in one genuine local-model attempt. Source was not changed or executed. Full semantic testing/repair and installed acceptance remain outstanding.
3. **Protected update path:** reconcile installed local candidate with future main updates; prevent an updater from discarding local fixes or treating an older published branch as a safe replacement. Verify exact workflow trust, schema compatibility and rollback.
4. **Thirty-one open PRs:** stacked fixes are not thirty-one independent missing features. PR #1 needs selective recovery; #28 finances and #41 review requirements are separately tracked.
5. **Owner-only vault and watchdog:** design and verify real privilege separation, redacted events, tamper resistance and shutdown authority. Schemas, sensitive-text filters and FileVault alone do not implement these runtime boundaries.
6. **Browser resource use:** earlier Chromebook CPU attribution was unproven. Check current dashboard hidden-tab polling and measure Mac behavior; do not reopen Chromebook performance work as a THRONE requirement.
7. **Private-data lifecycle:** audit logs, prompts, test artifacts, backups, exports and approved external calls all need scoped disclosure rules. Preserve histories pending retention approval, with disk-pressure alerts rather than silent deletion.
8. **Coordination truthfulness:** handoff words are lookup cues. Manual ChatGPT/Codex relay is not a running agent bridge. A text recovery dossier does not replace SQLite, code and configuration backups.

## Delivery and credit discipline

One active implementation package and one canonical evidence record at a time. Check current source and PR overlap before editing. Record a compact checkpoint after meaningful changes so later sessions read the delta. Use independent review where it closes a real security/release gate, not repeated whole-repository audits.

Planning does not require rerunning the already-passing 492 tests. During implementation, run the relevant checks, then the required integration/release suite once at the final revision; rerun only after changes or failures. Set a bounded objective and review checkpoint for each future Codex assignment. Do not start background agents, recurring monitors or duplicate device sessions by default. If accounting is unavailable, report usage/cost as unknown rather than inventing a dollar total. Codex development credits and Luna's local inference are separate budget concerns.

## Decisions needed to freeze the plan

The core direction is already settled. These are the remaining concrete decision gates, not a repeat questionnaire:

- **Current direction:** owner authorized reconciling this scope and proceeding through routine development. Missing original attachments remain recorded; compare them if recovered, without restarting completed work. Publishing/merging the review package and installing the tested change remain distinct decisions.
- **Stage 1:** choose an encrypted backup destination; decide whether login-required blackout recovery is sufficient. Keeping encryption and login is the default. UPS is optional.
- **Stage 4:** approve the concrete authentication/pairing/transport design and desired away-from-home access.
- **Stage 5:** approve the concrete isolated runner installation and any later narrowly scoped promotion authority.
- **Stage 6:** choose the first useful connector and notification destination; outside model spending remains zero unless explicitly changed.
- **Stage 7:** select a researched business pilot and its exact financial/communications boundaries.
- **Stage 8:** select voice/privacy preferences and final presentation from reviewable examples.

Engineering details should be resolved within these work packages. They should not force the owner to redesign the system or repeat settled answers. The reconciled plan governs the current work sequence. Missing original attachments and future sensitive implementation decisions remain explicit. No plan can establish that undiscovered defects do not exist.
