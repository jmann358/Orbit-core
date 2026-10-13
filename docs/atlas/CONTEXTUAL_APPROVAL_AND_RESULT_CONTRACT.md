# ATLAS review contract — one contextual Luna approval/result flow

**Status:** review-only UX/security acceptance specification for Flight Plan 1.0-RC F3, T08–T14 and T26; **not** an authorized edit to that unapproved plan, not a new permission API, not implemented by this document.

**Implementation coordination:** HELM owns integration source and PR #38. ATLAS owns this independent review document only. Before any UI implementation, reread latest `main`, PR #38, `luna/focus_ui.py`, `luna/approval_center_api.py`, `luna/goals.py`, `luna/receipts.py`, `app.py`; reuse existing SQLite task/approval/receipt stores and owner controls. Do not alter HELM's branch concurrently.

## What an owner sees

One persistent mission summary answers four questions without opening a separate development tool: **What is Luna doing? What does she need from me? What genuinely happened? Where is the result?** On the chat/task surface, show one context-sensitive card for the current mission and a small unobtrusive next-item count. The existing Approvals inbox remains the saved fallback for missed decisions. Technical reports stay expandable.

| Saved mission stage | Short owner-facing message | Primary choice | Truthful next state |
| --- | --- | --- | --- |
| proposed / planning | Goal, real ID, requested source, fixed proposed steps, expected outcome | Review plan | Awaiting approval only when a real pending action exists |
| pending approval | Exact action, why, target, risk, financial impact/unknown, scope, expiry/plan revision | **Approve / Modify / Reject** | Record decision first; show queued only if the actual executor has queued work |
| queued | Step queued and durable job ID; worker enabled vs recently observed state distinctly shown | View work; pause future claims | Running only after a real worker claim |
| running | Actual step, last saved event, worker observation time, no invented percent/ETA | View details; request safe pause | Next authorized step, next distinct decision, or recorded attention |
| attention / blocked | Real blocker, missing capability or failed step, whether effects already occurred | Inspect; revise/new approval; stop | Preserve partial outcomes and no unsafe automatic replay |
| draft ready | Proposed diff, trusted tests, tests not run, scope and independent review limits | Review draft | Never claim installed or released |
| completed | Objective, persisted worker result, independently verified flag, time, subresults, one direct link | **Open result** | Stable URL across refresh and restart |
| rejected / cancelled | Recorded decision and any already completed side effects | Details; propose new revision | No silent execution of the old action |

**Approval is not the same as completed execution.** Use a three-part trace: `decision recorded` → `job accepted/claimed` → `result recorded`. A healthy heartbeat alone is not an external-result verification. Do not mark work done because a REST POST returned HTTP 200 or model text claimed success.

## Boundaries and stale-state behavior

- The card is a projection of existing persisted mission, step, decision and job IDs; **no new competing task/approval database**.
- For the current fixed recipes, one approval authorizes exactly their recorded immutable allowlisted step list and existing worker continuation. No new external capabilities, paid work, source application, deployment or network access.
- For future consequential steps, the API must bind approval to **action ID + immutable plan revision/fingerprint + owner actor/session + scope + expiry**. The server revalidates at actual execution, not merely in the browser. Concurrent duplicates become one accepted action and a visible stale-state refresh.
- `Modify` creates a proposed replacement action or amended plan for review and makes old proposal revisions stale; it is **not** mutation of an already approved step under old consent. Until implemented, use truthful wording such as **Review plan / Create replacement plan**, not a control that pretends to edit in place.
- Reject, expired permission and revoked device must block the next claim, including after restart. The UI may show historical results, but cannot reapprove stale authorization by reusing a prior click.
- Never expose current unauthenticated localhost APIs to remote devices. Secure phone/tablet access requires separately approved authentication, transport, CSRF/origin defense, pairing/revocation and device tests; no mobile implementation is authorized here.
- Do not use `window.confirm` floods for normal permission handling. Show material risk in context and require a clear explicit action; preserve keyboard labels, 44px-class touch targets, accessible focus, readable errors and reduced motion.

## Narrow independent acceptance scripts for future implementation

These are proposed **tests**, not reported passes. Use synthetic SQLite and a real loopback server where indicated; on actual devices do not share private data into CI.

| Scenario | Procedure | Passing evidence |
| --- | --- | --- |
| A1 fixed goal approval | Propose an allowlisted two-step plan, view the card, approve once | Exact actions shown before approval; one durable decision; automatically queued ordered child jobs; genuine receipt |
| A2 no fake running | Disable worker, approve fixed goal, refresh/reopen | Shows approved/waiting with disabled/stale worker, **not** running |
| A3 concurrent click | Two browser tabs press Approve on same revision almost together | Exactly one decision and one child dispatch; other sees updated state without repeated action |
| A4 stale review | Open old card, change/reject proposal in other tab, submit original card | Explicit stale notice; no new work or permission broadening |
| A5 modify | Request modification of proposed step/scope | New pending revision with exact changed target, old authorization invalid; no work before new approval |
| A6 reject, pause, cancel | Reject before execution; pause while queued; cancel while work is already executing | No future unauthorized claims; disclose if in-flight action cannot be interrupted; preserve actual events |
| A7 step-two permission | First allowed step finishes, second requires different owner authority | Only second scoped approval appears; one approval is **not** interpreted as a blanket grant |
| A8 worker failure/restart | Interrupt worker after queued/claimed step; restart process | Bounded reconcile, no duplicate harmful side effect, attention if outcome uncertain |
| A9 result rendering | Complete goal, open link, refresh/restart, inspect on small screen | Same durable result with measurable outcome, provenance, verification label and explicit partial/failed states, not raw jargon alone |
| A10 real mobile authorization | After separate authorized secure pairing, approve from iPhone while iPad shows stale state, then revoke device | Only current authenticated action accepted; old session denied; both devices converge on one authoritative SQLite state |
| A11 accessibility/latency | Navigate via keyboard, screen reader and narrow portrait viewport with delayed POST/network loss | Focus stable; clear pending/ack/failure; action retriable without double-effect; no lost warnings |
| A12 budget/prohibition | Propose a paid call or source deployment from a fixed-goal card | Denied/no new permission; exact consequential operation requires distinct existing owner authority |

## Minimal implementation boundary if HELM adopts this

1. Preserve existing worker and `goals.decide_goal` atomicity. Add read-only task projection only where necessary to show real work in context.
2. Keep Approvals inbox as fallback rather than duplicating its business logic.
3. For a proposed fixed goal, show exact approved steps and genuine disable/block status; rename misleading controls before claiming modification works.
4. Make the JSON receipt machine-readable **and** offer a human-friendly result view, while keeping its `independently_verified` distinction and actual event/child-job provenance.
5. Implement future generalized consent/session/expiry only with separate owner-approved security design, not as incidental CSS/JavaScript behavior.

**Uncertified:** browser interaction, provider inference, Mac uptime, mobile pairing, live runner isolation, releases and backups. This review document changes no runtime authority, source code, personal records or network settings.
