# POJO HELM → THRONE | Section 03: Privacy, Memory and Retention

**Status: DESIGN READY FOR THRONE REVIEW.** This is an implementation contract, not a claim of a tested product or completed data migration.  
**Prepared:** October 12, 2026, America/New_York.  
**Inspected baseline:** [`jmann358/Orbit-core` draft PR #58](https://github.com/jmann358/Orbit-core/pull/58), exact head `560419de5f21102c9c9995de57dd4bb8890837f9`, **open, unmerged** when inspected. Published `main` remains a separate release; no live THRONE access from HELM. Reconfirm branch and installed revision before editing.  
**Requirements:** T03, T05–06, T20–23, T26, T30–34; V01–03, V05, V13, V16–18; intersects Sections 01, 02, 04, 05, 06, and 07.  
**Owner choices carried forward:** Retention C = **preserve existing conversation history and backups; no automatic permanent deletion until a retention policy is expressly approved**. Preserve original archived conversation history while allowing corrections, summaries and removal of obsolete facts from *active retrieval*. User's technical decisions are retained in a separate technical ledger; personal durable memories require explicit owner approval. Personal memory is only for owner/Luna; specialists receive only specifically authorized, minimized task context. THRONE remains authoritative single writer; any eventual free cloud blackout companion is restricted standby, not a second memory writer. Zero discretionary spending.

## 1. Outcome and non-goals

Luna must reliably retain useful context **without treating the conversation archive as permission**, publishing private history, fabricating memory, or persisting outdated claims as current facts. The owner can view provenance, approve/reject personal memories, correct or retire active memories without destroying protected history, and learn exactly what any model/agent will receive. A technical-decision record may be retained from a confirmed owner decision, but is not authorization to execute new capabilities.

Not authorized by this contract: deleting historical records or backups, switching on cloud AI or remote access, changing data retention, opening a public listener, contacting external accounts, creating a paid provider, copying memory to cloud, allowing other agents to query the owner's personal DB, or applying generated code. Full authenticated phone pairing = Section 05; cloud continuity/fencing = Section 06; Mac backup/restore acceptance = Section 04; code isolation = Section 07.

## 2. Source review: retain what's real, close the exact gaps

| Source | Established behavior at inspected SHA | Gap / required treatment |
|---|---|---|
| [`luna/core.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/core.py) | SQLite `messages` are persisted; `memory_candidates` start pending; only approved candidates and approved project notes enter model context; up to 30 recent turns are bounded; provider-specific model calls exist. | A single candidate approval field is not a versioned correction/retraction or scoped disclosure model. The approved-memory list and project notes join model context regardless of `continuity_cloud_enabled`; local content access and provider egress need separate gates. |
| [`luna/memory_suggestions.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/memory_suggestions.py) | Explicit “remember” cue, opt-in, heuristic sensitive-word exclusions, pending-only candidates, dedupe. | Heuristics are not a sensitivity proof, not complete classification, and can reject useful notes or miss secrets. They must not promote personal facts automatically. |
| [`luna/memory_learning.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/memory_learning.py) | Source-linked preview from saved **user** messages; review queue and blocked patterns; excludes internal sessions. | No versioned retraction/supersession, generalized conflict check, exposure audit or privacy-grade cross-session scope enforcement. |
| [`luna/continuity.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/continuity.py) | Lexical search across saved messages with bounded excerpts; historical text marked untrusted; can search other sessions. | Session string is not an access-control identity; retrieval should exclude retired/disallowed material from model context while retaining original archive, and must not leak personal text into specialist handoffs. |
| [`luna/continuity_settings.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/continuity_settings.py) | Local retrieval and cloud *older-excerpt* switches default off. | Neither setting alone authorizes sending the current chat, approved memories, or notes to a cloud model. A provider/data-destination preflight contract is needed. |
| [`luna/sensitive_intake.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/sensitive_intake.py), [`luna/sensitivity_policy.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/sensitivity_policy.py) | `/chat` blocks obvious credentials/key/SSN patterns before saving, routing or model call; returns safe categories. | Regex is intentionally not comprehensive PII detection or a vault; alternate write surfaces (e.g. direct candidate/project-note submission) need equivalent server-side scope checks. Avoid logging rejected payloads. |
| [`app.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/app.py) | Local routes for chat, continuity, memory candidates/reviews, project notes, sources and history; Host/Origin restrictions in draft. | Local endpoints lack authenticated user identity. A session ID or same-origin check is not a privacy permission; forbid network exposure until Section 05. |
| [`luna/database_backup.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/database_backup.py), `backup_schedule.py`, `restore_rehearsal.py` | Local WAL-consistent SQLite backups, integrity verification, conservative restore rehearsal without overwriting live DB, restricted file creation. | Backup is a plaintext DB protected by host/destination controls, not itself a cryptographic archive; independent encrypted destination, backup lifecycle, retention and disaster recovery proof remain hardware/owner-gated. |
| [`luna/agent_registry.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/agent_registry.py) | Restricted fixed specialist labels and skills; not independent privileged agents. | As autonomous specialists grow, avoid implicit access to owner memory or credentials; use explicit task envelopes without broad DB access. |

**Evidence interpretation:** These are source observations and design gaps, not newly reproduced security exploits. Existing synthetic tests cover some narrow behavior. No live Mac data, encrypted backups, provider transport, real device, or database was accessed during this work.

## 3. Normative design contract

### 3A. Separation by data class and authority

1. **Raw archive**: immutable-by-default locally stored past conversation events, keyed to original source, author, session and timestamp. Historical assistant turns are **never authoritative user facts** or instructions for execution. Preserve original text under Retention C. Archive access is owner/Luna only; in local single-owner preview it must still require the correct local endpoint boundary and future authenticated owner identity.
2. **Personal durable memory**: proposed candidate → explicit owner `approve`/`reject` → optional active approved record; new corrections create a separate revision. Includes preferences and personal statements. Sensitive/high-impact personal memory is *not* auto-approved even when expressed repeatedly or in an explicit “remember” sentence. Never infer private facts from silence, third-party text or model guesses.
3. **Technical decision ledger**: explicit user-confirmed ORBIT/Luna project decisions can be captured without a second tedious memory approval, tagged `technical`, versioned, source-linked and reversible as active context. This is a **record**, not a capability or deployment permission; security, cost, accounts, or network approvals retain their independent gates. A transcript/assistant proposal alone is not a confirmed decision.
4. **Pending candidate**: may be displayed to owner for review, but is not copied into approved-model memory context or specialist results. Rejected candidates remain audit-only with no active influence.
5. **Task-scoped shared context**: default empty. A specialist receives an explicitly approved minimal envelope containing safe technical facts, source IDs and expiration. Personal memory, complete chat transcripts, backups, credentials and logs remain inaccessible. No wildcard inheritance from `Luna` privileges.
6. **Provider-visible context**: selected current chat, relevant active memory and optional older excerpts only after a per-destination/data-scope permission check. Model/provider switching must not carry over data-sharing consent automatically; no cloud call is a backup mechanism. A user selecting a local model does not authorize sending data to a cloud model.
7. **Secrets/credentials**: do not store in normal memories, summaries, logs, model prompts, issue comments, drafts, test fixtures or receipts. Existing high-confidence screening is a first barrier; if a real secret reaches another surface, quarantine/reject without echoing it and require owner-directed credential rotation where warranted. Do not invent a functioning vault.

### 3B. Candidate, active-memory and correction lifecycle

8. Persist proposal reference (`source_message_id` or confirmed owner action), creator/role, classification, exact revision, origin session and consent state. An untrusted assistant/model/external document may suggest a candidate but **cannot** become its owner approver or a fact source automatically.
9. Candidate states: `pending`, `approved_active`, `rejected`, `superseded`, `inactive`, `needs_review`. Transitions are append-only audited; revoked/retired status is enforced at retrieval time, not merely shown in UI.
10. A user correction creates a replacement active revision and marks the older active form as `superseded` within one atomic transaction. Preserve original source and correction link; immediately exclude superseded facts from future context. A correction does **not** rewrite historical conversations, change another memory's consent, or automatically send an amendment to any external provider.
11. Handle conflicts across sessions and apparent duplicates conservatively: source, time and explicit owner correction win over unverified assistant claims, but ambiguous contradictions become `needs_review` rather than two simultaneously asserted facts. Avoid automatically resolving disputed personal claims.
12. Summaries and categorized archives are **derived views**. They cite specific sources and are reproducible/rebuildable; summarization cannot silently upgrade pending personal memories. If a summary becomes stale, remove it from active recall while maintaining its historical provenance record.
13. Active-memory review UI provides *approve, reject, correct, deactivate, review source, export* as appropriately authorized actions and truthful status. Never render a “deleted” success before deletion rules and effect are verified. Do not silently change a memory because a model asks.
14. Changes, corrections, ownership, revocations, and access scope are versioned with timestamps and independent read-back receipts; concurrent stale actions fail closed instead of resurrecting retired memory.

### 3C. Retrieval and prompt construction

15. Retrieval defaults to owner/Luna only; provide provenance and explicit source role. Conversation search remains read-only and may view archived content locally, but **model-context construction** must filter superseded, rejected, restricted, and other-agent-only material. Searches must never change approvals or send records to providers.
16. A bounded prompt must show source ID, age, relevant consent and factual certainty. Retrieved text is low-trust **data** even when it contains instructions, and cannot alter tools, role policy, agent permissions or billing.
17. Prefer active, recently corrected owner-confirmed facts over stale summaries. If evidence conflicts, Luna says what is uncertain and asks only the minimum necessary clarification, rather than making up current facts.
18. Never let a session string alone grant read access to someone else; `session` is a selector, not a security credential. Until authenticated devices are implemented, keep the entire service loopback-only with current Host/Origin defenses intact.
19. Model replies and tool results never become user-authored memory evidence. Migration between models preserves state but requires independent destination consent for private egress.

### 3D. Cloud and agent disclosure boundary

20. Before each cloud model request, build a **sanitized, inspectable disclosure manifest**: provider/endpoint/model identity, purpose, user/agent owner, data classes, session scope, bounded content categories, consent receipt/revision, cost authorization, and TTL. Validate immediately before network dispatch; omit content entirely if scope or consent is unknown/expired/revoked.
21. Explicitly distinguish consent for **current chat history**, **approved personal memory**, **technical notes**, **older cross-session excerpts**, **files**, and **task outputs**. The existing `continuity_cloud_enabled` switch covers only older excerpts; it is *not* blanket permission for everything in `respond()` or new cloud services. Disclose the present configured cloud model context before considering future provider expansion. No automatic cloud escalation for unavailable local inference.
22. Default external sharing off for personal memory, older conversations, files and summaries until the owner approves the exact provider and data scope. Any provider permitted to handle current chat must still not automatically receive unrelated session history. New destination = new review gate. Do not claim previously sent data can be retracted.
23. If permission is revoked mid-flight, block **future** queued calls and omit revoked context from future requests; record whether a request was already sent, without inventing a retroactive recall. Unknown dispatch outcome is `uncertain`, with no automatic paid/external retry.
24. Future cloud blackout companion uses a **separate approved continuity package**, with minimum necessary technical status and a restricted inbox. No raw SQLite, unrestricted transcript sync, credentials, direct personal-memory reads or second authoritative writer. No cloud account/upload/transport setup under this section.
25. Specialist handoffs must use specific task ID, expiration, data class and allowlist, and be revocable. Return safe summaries/verified task receipts rather than unfiltered records whenever possible.

### 3E. Sensitive intake, persistence, logs, backups

26. Sensitive intake validation must be server-side before every new durable write and outbound request path, not only `/chat`: memory candidates, project notes, learning submissions, tasks/agent prompts, exports, import and model/tool adapters. Block high-confidence secret patterns; do not falsely promise comprehensive PII detection. For ambiguous sensitivity, fail safely with clear owner review rather than echoing payloads.
27. Error messages, UI notifications, telemetry, usage counters, test artifacts, PR summaries and audits store sanitized metadata without secret contents or raw personal-memory excerpts. Any permitted exception is owner-reviewed and local-only. Test error paths, crashes and rejected values.
28. Under **Retention C**, disable automatic permanent deletion, backups pruning, age-based purges, log trimming that destroys required audit/owner history, and destructive migrations. **Active relevance is separate from physical retention**: outdated derived memory may be deactivated/superseded for retrieval without erasing the archive. An owner-facing future deletion function must show scope, copy/backup impact and restore limits, require explicit destructive authorization, and only report observed outcomes.
29. Owner export should be local, selectable by data class and time range, faithful to source/decision history, with a clear sensitivity warning, destination controls, re-import/version validation and no automatic cloud upload. Never pretend an export deletes cached provider data or protected backups.
30. Local SQLite is plaintext at the file layer, protected in practice by host encryption/OS permissions. Backups likewise require protected destination and encryption-at-rest where copied off-host; a SHA-256/integrity check is not encryption. Existing verified source backup/restoration tools must be reused. No direct upload of memory, WAL/SHM, hashes of private DB content, transcripts or credentials to GitHub, HELM chats or public logs.
31. Backup/restore must preserve approvals, revocations, corrections, ledger events, provenance, consent scope and current active state, not just `PRAGMA integrity_check`. Restoring an *older* snapshot must not silently resurrect revoked external access or outdated active memory. Use a quarantined restore gate with reconciliation and owner review; do not run restored agents/providers before reconciling.
32. New migration/additive schemas must support existing SQLite data without re-migrating, overwriting, deleting or changing the sole authoritative writer. Migrations stage on disposable copies; rollback stays possible and archival preservation is tested.
33. Classify operational audit metadata separately from raw private content; status and error views must never become a backdoor to personal history. Store minimal actor/decision IDs and redacted explanations where appropriate.

## 4. Minimal implementation architecture for THRONE (proposal, not mandate for a rewrite)

Keep existing `messages`, `memory_candidates`, `project_notes`, `continuity`, `core.connect`, `backup` and `agent_handoffs`. Prefer **additive** tables/columns or a small append-only ledger over destructive mutations:

- `memory_versions`: stable memory ID, revision ID, data class, active flag, source role/ID, origin session, classification, content reference, supersedes ID, created/approved timestamps. Access to content restricted to Luna/owner. Do not hash secrets into visible artifacts.
- `memory_decision_events`: old/new revision, action, source of authority, time, actor identity (future owner auth), immutable decision and reason code. Do not log secret payload.
- `context_disclosures`: one sanitized metadata receipt per cloud/agent disclosure with provider + scope fingerprint, class counts, consent revision and dispatch outcome; **no raw context in logs**.
- `memory_correction_links`: older/newer revision pair and owner confirmation; one transaction prevents stale resurrection. A pending correction is not automatically approved.

Existing `approved_memories` and `project_notes` become projections over currently approved active revisions; legacy approved records import as legacy approved only after migration checks and local owner reconciliation when provenance is missing. Do not manufacture historical approvals. Introduce centralized `build_authorized_context(...)` and provider-bound `preflight_disclosure(...)` guards; those guards should be testable without any real private data or network. No new general-purpose agent process or cloud database is needed.

## 5. Required threat cases and severity

| Priority | Threat | Mitigation / failure behavior |
|---|---|---|
| P0 | Cloud model receives personal memory or session excerpts without explicit appropriate sharing grant | Deny request or strip unapproved class, return meaningful consent prompt. Current-chat provider configuration must be shown truthfully, not conflated with old-excerpt switch. |
| P0 | Agent/tool retrieves private memory through a generic session ID, task link or local file | Deny; task-scoped explicit envelope only. Mac OS and DB permission separation remain an implementation/security acceptance gate. |
| P0 | Secret accepted via direct candidate/project-note/import path bypassing `/chat` screening | Apply centralized pre-storage and pre-egress validation; reject safely, never echo. |
| P0 | Corrected or revoked memory resurfaces after restore, cache, concurrent edits or agent work | Versioned active-state enforcement, restore reconciliation, no auto-activation until verified. |
| P0 | Raw database or backup, WAL/SHM, transcript, fingerprint or environment secret leaves host | Block outbound/private artifact exposure; no public logs or repository upload, independent review before any approved encrypted export. |
| P1 | Wrong/old memories presented as current fact | Provenance, correction precedence, conflict status and age signal; abstain when uncertain. |
| P1 | Model-generated/assistant text becomes an approved user fact | Owner-source validation and separate approval; prompt-injection safe labeling. |
| P1 | Provider-change silently continues previous sharing scope | Per-destination consent and scope/version validation each dispatch. |
| P1 | Consent revoked while a request is in flight | Stop future calls; record already-sent/unknown honestly; never promise retroactive deletion. |
| P1 | Data export or deletion claimed without physical verification | Receipt with actual file/artifact IDs and verification; Retention C prohibits automatic destructive operations. |
| P1 | Recovery snapshot restores old active grants | Gate restore on reconciliation; fail closed for providers and agents until owner confirmation. |
| P2 | Insufficient lexical recall or repeated project-note suggestions | Rank/provenance improvements and dedupe, but not at expense of confidentiality or correctness. |

## 6. Interaction with earlier sections

- **Section 01**: Approval must be actor/scope/revision-bound with replay resistance; memory decisions use the same conceptual atomicity but never piggyback on task approvals. Any new permission grant requires a distinct owner action.
- **Section 02**: A memory-export success, backup success or provider data-sharing outcome requires a task-specific evidence receipt. `200 OK`, worker reported success, SQLite integrity only or an unverified model statement do not prove confidentiality or restore correctness.
- **Section 04**: Real Mac FileVault/login/backup location/second-medium restore, boot recovery and backup retention evidence are still Mac/owner gates. No memory copies made from HELM.
- **Section 05**: Implement owner authentication, device pairing, session scoping, expiration and revocation before lifting loopback-only restriction. App `session` strings are never identity.
- **Section 06**: Cloud standby remains a no-second-writer, minimal continuity package; separate explicit connection/data transfer approval. Retention C remains in force.
- **Section 07**: No generated code, model subprocess or sandbox guest sees raw personal memory, credentials, backup directories or privileged history without an independently approved specialized capability.

## 7. THRONE implementation sequence and acceptance gates

1. **Reconcile reality once:** exact `main`, PR #58/current head, installed THRONE source, migration history, separate private backup; collect only sanitized metadata. Do not downgrade/replace recent installed code with published `main`.
2. **Implement privacy P0:** separate cloud current-context vs approved-memory vs older-excerpt grants; before-storage and pre-egress checks on all relevant routes; block agent personal-memory access. Maintain legacy local chat and review behavior.
3. **Add versioned corrections/retirements and provenance:** no deletion; technical ledger separate from personal candidates; atomic conflict guards. Migrate disposable synthetic DB first, then owner-approved backed-up local DB if needed.
4. **Integrate UI and receipts:** inspect source, review scope, correct, deactivate; show cloud disclosure manifest and what cannot be taken back; stable revision-linked audit/proof. UI views do not auto-consent or auto-share.
5. **Run the 72 synthetic acceptance cases** in `03_PRIVACY_MEMORY_TEST_MATRIX.csv` against real integrated code, plus pre-existing memory/continuity tests and Section 01/02 overlapping cases; run negative leakage and concurrency tests with fake secrets and disposable DB only.
6. **Exact-head reviewed tests** after any source change. Run final trusted suite once at release gate; independent ATLAS-equivalent review of changed code, especially data egress and database migrations.
7. **Mac acceptance with owner permission:** preservation snapshot, verify encrypted destination and no extra writer, test recall/correction/export on fabricated records or approved safe examples, test local provider/context audit and revoke/restore reconciliation. Do not use real personal content in GitHub/ChatGPT artifacts.
8. **Report outcome truthfully:** `design ready` ≠ `draft integrated` ≠ `synthetic tests pass` ≠ `Mac privacy/recovery acceptance pass` ≠ `owner accepted` ≠ `released`. Do not merge/install/publish or enable any service without separate explicit authorization.

## 8. Design closure and reopening policy

Section 03 can be marked **DESIGN READY** once this contract, matrix, source anchors, threat table and owner preference carry-forward are complete and internally consistent. Reopen only when fresh THRONE code contradicts a specified behavior, new evidence identifies a real privacy/security risk, the platform or API changes materially, or the owner explicitly changes the policy. A failing implementation test creates an engineering fix, **not** a reason to repeat all design decisions.

**Not yet verified:** functional integration, private memory correctness on real Mac, actual cloud consent enforcement, authenticated multi-device isolation, off-device encryption, restore reconciliation, privacy deletion behavior, real provider outputs. No GitHub changes, code deployments, real model calls, new cloud accounts, private DB reads or network exposure occurred while preparing this document.
