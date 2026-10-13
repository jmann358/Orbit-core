# POJO HELM → THRONE | Section 01: Mission Approvals and Lifecycle

**Status:** DESIGN COMPLETE FOR THRONE REVIEW — implementation and real-device acceptance OPEN.  
**Prepared:** October 12, 2026 (America/New_York)  
**Baseline inspected:** `jmann358/Orbit-core` draft [PR #58](https://github.com/jmann358/Orbit-core/pull/58), head `560419de5f21102c9c9995de57dd4bb8890837f9`, **unmerged**. Published `main` is reported as `pojo.2`; THRONE's installed source is reported, not inspected live from HELM. Re-fetch before implementation.  
**Acceptance register coverage:** T01–T03, T05–T06, T08–T16, T22–T26, T33–T34; V01, V13–V18; related Stage 3 and Stage 4 gates.

## Decision in one sentence
A Luna mission is a durable, versioned **owner-bounded commitment**: it can execute only its explicitly approved steps; its controls must remain in the same task context; every state transition, interruption, modification and result must be truthful and recoverable; no worker claim alone proves success.

## 1. Source-grounded starting point: keep rather than rebuild

- `luna/goals.py`: fixed allowlisted steps; goal proposal in a transaction; `decide_goal` approves/rejects only a proposed goal with `BEGIN IMMEDIATE`; `advance_goals` queues sequential work; `control_goal` pauses, resumes, cancels future claims, but running handlers might finish. Preserve all these strengths.
- `luna/jobs.py`: bounded queue, atomic duplicate avoidance in `queue_once`, restart marks interrupted running jobs as `attention` instead of replaying; only certain read-only checks retry. Preserve this behavior.
- `luna/mission_consent.py`: development-model grant bound to existing queued owner mission, endpoint/model, one hour, up to two requests, consumed before request; revoke currently only works if **unused**. Do not reinterpret revocation as undoing already-started calls.
- `luna/chat_mission_ui.py`: `selected=pending||ongoing||list[0]` can obscure running work with a pending proposal; supports approve/reject but says to reject-and-recreate for modification.
- `luna/focus_ui.py`: selects the first goal in broad active-state list, so pending and active work cannot both be reliably prominent; also uses reject-and-recreate for changes.
- `luna/receipts.py`: correctly declares `independently_verified=False`; worker-reported completion and independently established outcomes are not yet the same thing.
- `app.py`: goal decision endpoint accepts a boolean; local source has Host/Origin protections but no authenticated remote owner pairing. Keep loopback-only until a separate remote-auth design is approved.
- `docs/ACCEPTANCE_REGISTER.md`: explicitly marks T10–T15 and mobile-device cases partial or unverified. Do not substitute this document for successful tests.

**Out-of-scope for this section:** full natural-language planning, Mac sandbox execution, revenue generation, external deployments, remote phone access, enabling paid models, cloud standby failover or database replication. These have their own work packages. A free cloud blackout companion is a newer owner requirement and does not grant second-writer authority.

## 2. Settled functional contract (normative)

### A. Scope and authority
1. Every proposal has a durable goal ID, immutable revision, ordered step list, allowed tool kinds, scope boundaries, resource/time limits, evidence criteria, and source reference if applicable. Never execute instructions embedded in a title or fetched content.
2. A user approval applies **only** to the displayed revision and its step list, not to future edits, a similarly named task, another model, or additional permissions. Store an integrity digest or version for deterministic binding; a hash is **not** authentication or approval.
3. Preserve one authoritative mission database writer on THRONE. No phone, tablet, old Chromebook, or blackout companion may independently commit the same canonical mission history.
4. Owner review is mandatory for scope expansion, access escalation, new provider/model/data destination, paid request, executing model-generated code, installation, release, remote exposure, or external real-world side effects. Lower-risk already-approved fixed steps continue without repeated prompts.
5. Existing working budget and consent restrictions apply **at dispatch and at the consequential action boundary**. No implicit renewals. A model-generated suggestion cannot authorize itself.

### B. Proposal revision and modification
6. **Before approval:** “Modify plan” creates a replacement revision linked to its predecessor, displays an explicit diff, and requires a fresh approval. The predecessor stays in audit history and cannot later be approved or dispatched. The UI can display “Modified — awaiting approval,” not “Approved.”
7. **After approval but before dispatch:** modification withdraws permission for future claims under the old revision; creates a new proposal; no edited step runs without a new affirmative approval. Previously recorded decisions remain immutable.
8. **After any step started:** never rewrite history or silently cancel a handler already running. Pause future claims; record the in-flight step as *possibly still executing*; reconcile its observed result before creating and approving a successor plan. Show carried-forward/completed steps as history, not newly approved work.
9. **Reject:** terminal for that revision, with no dispatch. Subsequent attempts to approve a rejected, superseded, expired or already-approved revision fail safely. Existing reports remain readable.
10. A modification is a **first-class user action** in the mission view, not a requirement to navigate another tab and manually retype an entire plan. Implementation may use a server-side replace API or a transactional reject-and-successor call, but must preserve linked history and anti-race behavior.

### C. Lifecycle and interruption semantics
11. UI should distinguish `proposed`, `approved/waiting`, `running`, `paused`, `attention/uncertain`, `cancel requested`, `cancelled before execution`, `worker-reported complete`, `verified complete`, `rejected`, and `superseded`. These are **semantic presentation states**; do not require an unreviewed wholesale database schema migration. Map existing states first; add only what is essential.
12. **Pause:** prevents new claims; work already in progress may finish. UI says exactly that. Resume must re-check the original approved revision and still-valid grants.
13. **Cancel:** block unclaimed work immediately. For a running handler, record *cancel requested, in-flight result unknown* until reconciled. Never claim a network request, model call, payment or other side effect was reversed without independent confirmation.
14. **Restart/crash:** preserve the event log and task IDs. Running work recovered as `attention/uncertain`, not automatically replayed. Reconcile side effects before permitting an explicit retry. Retry budgets and idempotency keys apply to effects, not just database rows.
15. **Revocation/expiration/provider changes:** block future claims and future external requests. Already-consumed requests remain charged/used in the audit even if the response is missing. Client disconnection is not an approval revocation or a cancellation by itself.
16. **Resource limits:** queue, retry, capacity and $0 discretionary cloud/paid budget are server-enforced. If cost is unknown, fail closed rather than silently trying a paid provider.

### D. Inline, sequential interaction
17. The **primary mission card follows the mission being worked on**, even if a different proposal is pending. Pending approvals are shown as a separate context-tied item or count, never in place of a running mission. A blocked mission shows its blocker and safe next action.
18. One task → approval at the precise boundary → progress (with saved step/worker states) → verified or unverified result → direct durable result link. Reveal the exact actor/action/target/scope/impact at sensitive boundaries. No parallel approval maze or page-switch requirement.
19. Approval, rejection, and modification controls use server state as authority. Disable during submission; after a timeout query the stored decision before offering retry. Do not treat an uncertain HTTP result as permission.
20. Two tabs or devices deciding against the same revision yield **one committed decision**. Stale clients receive a conflict, refresh current state, and cannot create a second child job or expand scope.
21. On screen reader, mobile narrow viewport, lost connection, refresh, and delayed progress updates, the mission and correct action remain legible. The card does not infer worker liveness merely from `running` stored state.

### E. Result and independent proof
22. A worker saying `completed` means **worker-reported complete** only. For independently verified status require a separate verifier, evidence linked to the exact goal revision, step/job IDs and relevant source commit, and reproducible observations against declared success criteria.
23. Verification is task-type-specific. A local health result proves only named checks; a GitHub CI success must match the **exact source SHA, workflow and conclusion**; a development proposal is not evidence of safe execution; a mock or test fixture must never be represented as a live model/Mac outcome.
24. A failing, stale, incomplete, unavailable, contradictory or nonmatching verifier produces `unverified` or `attention`, **not** `verified`. Preserve worker report and verifier findings separately. Never manufacture a receipt when a verifier is unavailable.
25. Every finished or interrupted mission has a durable, access-controlled receipt with objective, plan revision, timestamps, authorizing event/reference, step/job states, worker outcome, verifier status/evidence/limits, retry/cancel history and direct link. No private transcripts, DB fingerprints or secrets in public GitHub reports.

## 3. Reference state transitions

| Current | Allowed trigger | Next observable state | Guard |
|---|---|---|---|
| proposed | owner approves exact revision | approved | scope/limits valid; atomic compare-and-set |
| proposed | owner rejects | rejected | cannot later be executed |
| proposed | owner modifies | superseded + successor proposed | predecessor never executable; diff persisted |
| approved | worker claims next authorized step | running | one writer; budget, grant, revision checked |
| approved/running | owner requests pause | paused for future claims | in-flight activity may finish |
| paused | owner resumes | approved/waiting | permissions revalidated; no blind replay |
| any cancellable | owner requests cancel | cancelled or cancel pending | in-flight uncertainty remains visible |
| running | worker claims success | worker-reported complete OR next step | never independently verified merely by state |
| worker-reported complete | independent checker confirms | verified complete | evidence applies to exact plan/task/revision |
| running | crash/ambiguous outcome | attention/uncertain | stop automatic replay; reconcile |
| any nonterminal | grant expires/is revoked | blocked/attention | future effects denied; history intact |

**Invariant:** a terminal revision cannot be reapproved; a verified completion cannot be based exclusively on worker prose or a green check for an unrelated commit.

## 4. Minimal implementation map for THRONE

1. **Contract migration, smallest possible:** extend `luna/goals.py` with an immutable revision link/digest and atomic successor operation; retain current step/job/event tables where feasible. Add a reversible migration only if justified by fixtures; test old database format against disposable copies.
2. **Decision preconditions:** extend the existing `app.py` goal decision pathway with explicit expected revision/version; keep backward compatibility safely or reject ambiguous legacy writes after migration. Preserve actual authentication boundaries (localhost is **not** remote identity proof).
3. **UI:** update `luna/chat_mission_ui.py` and `luna/focus_ui.py` together so active mission and separate pending decisions remain visible and consistent. Modification must use the canonical server operation, with diff/approval receipt.
4. **Worker guards:** use `luna/goals.py`, `luna/jobs.py`, and consent modules for atomic execution gates. No second queue; no speculative resume or automatic model-code application.
5. **Receipts:** extend `luna/receipts.py`/`luna/receipt_views.py` with separate verification status only after a real check is implemented. Do not flip `independently_verified` from false on the strength of the worker's `completed` flag.
6. **Regression suites:** extend `tests/test_chat_mission_ui.py`, `tests/test_inline_goal_approval.py`, `tests/test_mission_receipts.py` and targeted goals/consent tests. All privacy tests use disposable SQLite and fake endpoints.
7. **Verification:** run targeted tests, then compile and trusted full pytest suite at the final candidate SHA; inspect all changed PR ancestry and existing tests, avoid merges of stacked PRs twice. Host/browser/Mac-specific acceptance is a separate later gate.

## 5. Non-negotiable failure and security rules

- Approval is never inferred from model prose, successful tests, a prior generic “yes,” the receipt digest, a stale UI, cloud synchronization, a codeword, or an HTTP timeout.
- No generated code execution, paid request, external account use, remote service exposure, release or database deletion is authorized by this contract.
- No automatic retry after an ambiguous consequential side effect. Reconcile or escalate.
- No duplicate authoritative writer; remote/cloud standby gets a separate restricted continuity contract, not a hidden fork of this database.
- Preserve history even when the UI collapses it. Obvious secret screening does not replace private-data policies or remote authentication.

## 6. Planning closeout vs implementation closeout

**HELM design closeout:** The behaviors above are specified; each is traced to a source finding and QA scenario in `01_MISSION_APPROVAL_TEST_MATRIX.csv`. No new owner preference is required for routine design, and implementation may choose internal method names without reopening this section. This document is not an installed feature, a passing repository test, an owner-approved release, or a replacement for the current flight plan.

**THRONE implementation closeout:** Every applicable `MA-01..MA-28` test passes on the exact reviewed source revision, including negative/collision scenarios. Mac-browser tests and service restart pass on the actual Mac. Owner acceptance of the inline flow and of any new sensitive permissions is recorded. Current `main`, installed code and candidate SHA are distinguished. Only after those checks may this section be called **implemented/accepted**.

**Reopen ONLY when:** (a) a reproducible defect conflicts with a specified invariant; (b) a security/authority requirement materially changes; (c) new platform/API behavior invalidates an assumption; or (d) the owner deliberately changes scope. Each reopening records exact reason, affected requirements and delta; preserve settled decisions. Generic “review again” is not a reason.

## 7. Execution instruction for THRONE

> Read this contract and CSV alongside current issue #52, PR #58, `AGENTS.md`, `docs/ACCEPTANCE_REGISTER.md`, and live installed-source/CI evidence. Confirm exact source/head before editing. Implement the smallest reversible, test-backed change set for Section 01; preserve single-writer state, privacy and per-action approvals. First validate an active mission plus pending proposal appearing simultaneously, modification before/after dispatch, cancel-in-flight uncertainty, stale dual-tab decisions, and independent verification labels. Show the owner the actual Mac UI and evidence before requesting a merge, install, or release. Do not repeat HELM's broad planning audit.

**Source links** (re-fetch on THRONE): [PR #58](https://github.com/jmann358/Orbit-core/pull/58) · [Issue #52](https://github.com/jmann358/Orbit-core/issues/52) · [goals.py at audited SHA](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/goals.py) · [mission card](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/chat_mission_ui.py) · [receipts](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/receipts.py).
