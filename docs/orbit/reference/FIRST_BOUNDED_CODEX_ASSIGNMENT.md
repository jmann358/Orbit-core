# First Bounded THRONE / Codex Assignment — P0-1 privacy at provider egress

## Mandatory preflight
Read **latest** issue #52 comments, current draft PR #58, the Mac's installed Git SHA and service/memory status. Read original HELM Sections 03 (privacy) plus relevant 01/02 boundaries. **Only start source edits after an owner-approved encrypted independent backup/restore gate for newer Mac data.** No repeated global audit, no reset/merge, no changed model/provider, no private chat extraction.

## Strictly scoped objective
Using the currently installed baseline, inspect the actual call path that constructs a cloud model request. Establish independent, server-enforced, default-deny authorization for **(a) current chat turn, (b) approved personal memory, (c) older raw history/retrieval, (d) attachments or private files, (e) technical operational facts.** Existing `continuity_cloud_enabled` only concerns a subset; don't mistake it for blanket cloud-disclosure control. Preserve ordinary local Ollama behavior; cloud stays disabled by default. Owner consent must bind provider/endpoint, data class, purpose, expiry and revocation. Never store API keys or contents in audit logs.

## Execute in these increments
1. Inventory current actual egress path(s), opt-in settings and tests; record the exact SHA. If cloud model path does not exist, produce a reviewed design delta instead of inventing a transport.
2. Write **synthetic failing tests** for consent-off, wrong provider, stale/revoked consent, forbidden memory data, allowed narrowly scoped synthetic content and test response handling. Check current chat separately from retrieved history. Ensure the check happens **immediately before dispatch**, not only in a UI form.
3. Make the smallest source change reusing Luna's existing privacy/consent/settings components and avoiding migrations unless unavoidable. Never call a real cloud provider in tests.
4. Run targeted privacy/consent tests first. On a stable final diff run the relevant integration/full repo suite once. Record exact command, commit/tree and results; if expected behavior cannot be proven, mark BLOCKED, not green.
5. Produce a concise reviewable diff and evidence in the acceptance execution ledger. Do NOT auto-apply, install, publish/merge, start a new listener, enable remote access or change credentials.

## Exit conditions
No current chat/memory/history/attachments are disclosed without their separate current permission. Denied calls do not send, enqueue, consume budget or log private content. Local-only ordinary chat still passes. Race/restart and provider-switch negative tests fail closed. Unauthorized schema edit or conflicting privacy setting cannot bypass dispatch gate. Any remaining classification uncertainty is reported plainly.

**If the independent backup gate is missing, STOP after read-only review.** Request only the concrete owner choice of encrypted destination. Once gated, proceed with bounded source+synthetic tests. This is not authorization to publish or deploy.
