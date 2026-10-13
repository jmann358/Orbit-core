# POJO HELM → THRONE | Section 02: Evidence, Independent Verification, and Honest Results

**Planning status: DESIGN READY FOR THRONE IMPLEMENTATION REVIEW.** Not implemented, independently audited as a code change, Mac-tested, owner-accepted, or released.  
**Prepared:** October 12, 2026 (America/New_York).  
**Source baseline:** `jmann358/Orbit-core`, draft [PR #58](https://github.com/jmann358/Orbit-core/pull/58) at `560419de5f21102c9c9995de57dd4bb8890837f9`. This head was rechecked during HELM's Section 02 review; it remained open/draft/unmerged at the moment of review. Re-fetch exact `main`, candidate, and installed service revision on THRONE.  
**Acceptance references:** T01–T04, T07–T09, T14–T16, T17–T18, T20–T26, T28–T30, T32–T34, V01–V03, V11–V18; Section 01 MA test matrix and its consent/lifecycle invariants. This section does **not** declare those wider gates complete.

## 0. Normative decision

A saved Luna *job state* and an independently established *outcome* are separate facts. Luna must never mark a mission as independently verified just because a worker returned success, a model declared completion, a test suite was green, a stored hash matched, or the UI received HTTP 200. Independent verification is a new read-only observation, conducted through a trusted path separate from the worker's success assertion, against **predeclared, bounded success criteria** and matched to the **exact job/attempt, approved goal revision, data/source version, relevant provider/workflow, and observation time**. A verification can prove only the stated scope. Nothing in this section grants execution, spending, remote access, deletion, deployment, or new model/provider permissions.

## 1. Verified source facts — preserve, don't rebuild

1. `luna/jobs.py` stores durable jobs and events with states including `queued`, `running`, `retry_wait`, `completed`, `attention`, `cancelled`. `finish_job()` records a **worker-reported** result; `recover_interrupted()` marks previously running work `attention` rather than replaying it. This is good and must remain.
2. `luna/goals.py` tracks fixed allowlisted steps and sequential child jobs. An objective and existing completed-step count do not establish external success; goal completion is derived from approved step/child job records.
3. `luna/receipts.py` projects existing records to read-only job and goal receipts. It *explicitly* sets `independently_verified: False` and detects inconsistent goal/child completion. Keep receipts backward compatible and authoritative only as a **view** of saved evidence.
4. `luna/receipt_views.py` escapes stored text and warns that completion is worker-reported. Preserve safe rendering, audit links, and this warning whenever verification is absent.
5. `app.py:_process_job`: `project_health` summarizes limited syntax/file/source-inspection checks as `Health x/y`; `github_status` checks the latest GitHub workflow run without binding it to the assessed exact commit; `development_plan` returns `planning_report('DEV-003')`. These do **not** currently prove mission-specific external effects or independently selected development conclusions.
6. `app.py:github_checks()` currently extracts run name/status/conclusion/branch/timestamp/URL, but **not** `head_sha` or the trusted workflow identifier; an unrelated successful run can otherwise be mistaken for evidence for the candidate being assessed.
7. `tests/test_mission_receipts.py` checks persistence, direct links, and inconsistent completion, including `independently_verified=False`. Implement by **extending** these modules/tests, not by introducing a parallel job system.
8. Existing HELM standalone `evidence_priority.py` and its 15 synthetic tests classify sanitized source/CI snapshots; `verify_report_against_snapshot` checks *consistency only*, expressly **not independent external outcome verification**. Reuse ideas selectively; do not wire its `consistent` field directly into a verified receipt or treat its accepted snapshot as a trusted external observation.

### Existing hard constraints

Single authoritative THRONE database writer; no raw private SQLite data sent to GitHub/chat; preserve source backups and events; `$0` discretionary provider spending; no unapproved cloud, accounts, network access, generated-code execution, merge or install. A cloud blackout companion may provide restricted read-only/queued continuity only under its future approved contract, never become a second authoritative verification or memory writer by accident. Issue #52's owner amendment supersedes stale sole-host/no-cloud wording in the draft flight plan.

## 2. What "independent" means — **bounded assurance levels**

Use two distinct axes in stored records and UI: **worker execution** (`queued/running/completed/attention/cancelled/...`) and **verification** (`not_checked/checking/verified/failed/inconclusive/stale/not_applicable`). This is a presentation/API contract, not a demand to rename current job database states.

- **Worker-reported:** same actor/worker/LLM that performed a step claims completion. May be useful history but alone has zero independent verification authority.
- **Integrity/consistency checked:** deterministic recomputation establishes that a *provided* snapshot/report or hash is internally consistent. Does not prove snapshot origin, real-world effect, model correctness, or actual GitHub/Mac condition.
- **Independently verified within scope:** separate trusted checker obtains/re-observes an authoritative read-only source, independently evaluates *predeclared criteria*, and durably records matched IDs, scope, time, trust source, and outcome. The verifier should have narrower read-only authority than the action being checked. It may run in the same trusted service process for a narrow local check, but must not simply trust the worker's `success` flag or model output. If the source itself could have been forged by the worker, it is not independent proof.
- **Owner-confirmed observation:** an owner expressly confirms a perceptible or physical result and the saved record identifies it as **owner attestation** (with scope/time), not mechanical independent verification; use only for user-observable outcomes that cannot be independently instrumented. Never infer this from chat prose without the exact action-specific confirmation.
- **Unverifiable subjective/creative work:** a reviewer can confirm a file/draft exists and constraints passed, but cannot prove subjective quality or business impact automatically. Label `artifact checks passed / human review needed`, not `independently successful`.

**Verification statuses:**

| Status | Required meaning and UI label |
|---|---|
| `not_checked` | No independent checker has completed; label **Outcome not verified**. |
| `checking` | Saved attempt pending or underway; avoid implying success from progress. |
| `verified` | All mandatory, scope-appropriate evidence and criteria pass for the matched frozen version; show **Verified for: [narrow scope] as of [UTC time]**. |
| `failed` | Trustworthy checker establishes a criterion failed or the worker's outcome contradicts observed facts; show the mismatch, not just error icon. |
| `inconclusive` | Missing, inaccessible, untrusted, contradictory or insufficient evidence; **never** imply success. Distinguish an outage from a confirmed defect. |
| `stale` | Earlier verification was valid for an older snapshot/source/result/expiry but does not establish current state; preserve original event with **Verified previously as of ...; current state unknown**. |
| `not_applicable` | Only when the contract explicitly calls for human/subjective review or a non-verifiable claim; never a shortcut to mission completion. |

Note: `failed` here means **verification failed a declared requirement**, not necessarily worker execution failure; don't rewrite job history. `inconclusive` is not a user rejection, and `stale` is not retroactive fabrication. The UI can summarize; the underlying ledger preserves the exact prior statuses and evidence events.

## 3. Evidence and ledger data contract

Extend the **existing** goal/job/receipt event model with bounded append-only verification records (new table or existing durable event mechanism; choose smallest safe migration on THRONE). Avoid a second authority or shadow mission queue. Minimum immutable fields:

| Field | Purpose and invariant |
|---|---|
| `verification_id`, `schema_version` | Unique record and explicit version; duplicates handled idempotently. |
| `job_id`, `attempt_id_or_number`, `goal_id`, `goal_revision` | Bind to exactly the authorized attempt; for standalone jobs `goal_id=null`. Do not silently carry success across a new revision or replay. |
| `criterion_id`, `criterion_definition_version`, `required` | Criterion was fixed *before* execution and reviewable when owner approved the plan; verifier cannot rewrite it to make a failed job pass. |
| `scope_label`, `covered_capabilities`, `limits` | Plain-English statement of **what was and was not proved**. |
| `subject_fingerprint`, `source_commit_sha`, `artifact_revision` | Bound to inspected data/result/code when applicable. SHA-256 is integrity metadata, not trust or owner approval; no hashes of private conversations or DB contents in public artifacts. |
| `checker_id`, `checker_version`, `checker_trust_boundary` | Identify independently implemented read-only verifier/adapter and whether it is distinct from the execution producer. Do not call an LLM judge independent by default. |
| `evidence_kind`, `evidence_ref`, `observed_at_utc`, `collected_at_utc` | Provenance to trusted local artifact/fixture/external API response; use allowlisted **internal paths/IDs**, not arbitrary model-supplied URLs. |
| `status`, `failure_code`, `evidence_summary`, `expiry_at_utc` | Machine decision plus redacted human-readable reason and freshness budget. Unknown mandatory fields fail closed. |
| `audit_event_id`, `verification_group`, `replaces_verification_id` | Append-only trace for rechecks/supersession, atomic commit, grouped criterion verdicts. |
| `origin_class` | One of `live_local`, `authenticated_external`, `owner_attestation`, `synthetic_fixture`, `model_reported`, `self_consistency`. `synthetic_fixture` never supports a **live** completion badge. |

Every result receipt must return at least: saved worker state, worker-reported result, `verification_status`, `verification_scope`, `verified_at` (nullable), `verified_for_version` (nullable), `independently_verified` (derived **only** from mandatory trusted verification records), evidence items (redacted and access controlled), `verification_limitations`, audit trail, and a stable direct result URL. Preserve legacy keys; new fields default to `not_checked` and false for old records, never synthesize a successful backfill.

**Failure handling:** event writes and final receipt projection use consistent transactions; if checker crashes after reading but before saving, show `inconclusive`/`checking interrupted`, never `verified`. If a duplicate callback races, upsert/idempotent key ensures one decision per attempt/criterion/evidence version. Store change/expiry facts as new events, not overwritten history. A public-facing export includes sanitized explanations and safe references only.

### Verification request identity

Recommended idempotency key: `(job_id, attempt_number, criterion_id, subject_revision, checker_version)`. A request repeated with *different evidence* must create a new observation version/event and must not silently replace a prior verdict. Concurrent observations with conflicting claims become `inconclusive` and require review. If the worker can modify source/output while verification runs, take a safe immutable snapshot (when possible) or re-check the subject revision before committing success; otherwise classify `stale` or `inconclusive`.

### Criteria registration and authority

Verification criteria can be registered by a trusted, versioned allowlisted recipe, or attached to an owner-reviewed immutable plan. A model's suggested criterion is **untrusted text** until owner-approved and bounded. Requirements may be tightened only through a new reviewable revision, not relaxed post hoc. A criterion may have a freshness TTL, but TTL alone is insufficient when an observed mutation or provider/revision change invalidates it immediately. Use UTC and bounded clock skew; inconsistent clocks are `inconclusive`.

## 4. Task-specific proof contract (initial supported mission kinds)

### 4A. `project_health` — scoped local readiness only

**Declared criterion:** requested trusted checks (syntax, expected file presence, specific source finding codes) actually executed against a named trusted source commit/worktree snapshot and passed. A *separate* read-only validator repeats/checks declared indicators from the pinned source, not the worker's `Health x/y` summary. If root/path is unsafe, source changes during reading, checks are incomplete, or file system is inaccessible: `inconclusive`; a confirmed failed check: `failed`. Output must say **"Source health checks [names] passed at [time]"**, not "THRONE healthy," "Luna online," or "Mac stable." Actual inference, service uptime, disk, real browser and memory persistence are distinct Mac gates.

### 4B. `github_status` — exact source/workflow CI, not latest green run

**Declared criterion:** a trusted GitHub API response for **exact repository, 40-character `head_sha`, expected workflow ID/path, completed status, and successful conclusion**. Require the run's observed `head_sha` and workflow identity, plus trustworthy retrieval time and URL/ID; filter on requested exact candidate SHA before selecting a run. A wrong branch/head/workflow, PR fork, `in_progress`, `neutral`, absent check, or conflicting latest matched runs cannot verify the candidate. A completed exact-run failure may yield **failed CI criterion**; a transport outage or insufficient response yields `inconclusive`. If checking multiple required jobs, require all exact expected job conclusions/commit references, not just the first run's aggregate text.

**Scope:** A passing workflow proves **those listed tests passed for that specific GitHub source SHA**, not that Luna is installed, production-ready, safe, fully correct, or executing on the Mac. If no source identity exists, do not manufacture an exact SHA. Validate safe, allowlisted GitHub run URLs on output.

### 4C. `development_plan` and evidence-based issue selection

The currently hard-coded `planning_report('DEV-003')` is not an independent investigation. A real plan must cite the **separately obtained** pinned health/CI evidence; classify one actionable issue *only* if a verified failing criterion supports it. Allow legitimate `no_supported_issue_found` and `insufficient_evidence` outcomes. A deterministic validator can check exact provenance, priority policy, allowed next step and faithful description of sources. This can be marked **"evidence consistency checked"**, **not automatically "independently verified solution/correct diagnosis"**. Proposing a solution requires review; no auto-apply or permission change.

### 4D. `workshop_draft` / developer model proposals

Verify a *review-only artifact* exists, is bound to expected file/revision, is parseable under existing safe validators, is untampered, and was **not** executed or installed. A proposed patch reaching `review` proves preparation, not that it works. Syntax passing and fingerprint matching do not prove security, correctness, or sandbox isolation. No change to live files, dependencies or permissions without separate gates. Future sandbox proof is Section 07, not this section.

### 4E. Persistent memory, browser workflows and future external effects

For message persistence use a controlled (authorized) client/session plus durable read-only query after a verified service restart on THRONE, with privacy boundaries and no raw transcript export; synthetic database tests alone are labeled synthetic. For future emails, financial operations, uploads, service changes or external submissions, require **separate permitted authoritative read-back** or explicit owner attestation with effect ID, target, scope and uncertainty. A server returning 200 or worker claiming it sent an email is *not* proof of delivery. If authoritative read-back is unavailable, status remains `inconclusive`; do not auto-retry uncertain consequential effects.

## 5. Aggregation rules and lifecycle integration

1. A job may become `worker_state=completed` while `verification_status=checking`, `failed`, `inconclusive`, or `stale`. **Do not overwrite** its worker state; show both.
2. A goal's **verified** result requires *all mandatory approved steps* to have applicable passing verification bound to exact job attempts and criteria, plus any separately declared mission-level postcondition. A goal can be `worker_reported_complete=true` while `independently_verified=false` if any mandatory criterion is missing; the goal is never verified from step count alone.
3. Optional/subjective criteria must be predeclared and visible. If human review is mandatory, goal status says "review required" even when machine-checkable steps pass. No silent `not_applicable` substitution for required criteria.
4. Rejection, supersession, consent expiration, cancellation and restart must not cause old verification to authorize future work. Old evidence stays visible with scope/version and time, but subsequent attempts require their own verification. In-flight/unknown side effects do not become verified solely because a cancellation was recorded.
5. Verification itself is **read-only and budget-limited**. If a check requires outside network access, model usage, private file access or monetary cost beyond already-authorized scope, pause and ask for specific permission; a verification requirement never expands authority.
6. Live read-back checks should be allowed only from trusted allowlisted adapters. Treat all fetched page text, PR descriptions, model output, user-entered paths and file contents as untrusted data. Verifier must never execute instructions found there or follow arbitrary URLs. Credential-bearing diagnostics/requests are not shared publicly.
7. When a later recheck finds changed conditions, append `stale`/new verdict while retaining earlier proof as a historical `verified as of ...`. Distinguish **historical acceptance** from **current status**.

## 6. UI/UX acceptance: same task, one trustworthy result

At the end of each mission, the chat/home inline mission card shows: objective, bounded scope, job and goal revision, worker's reported outcome, one of the verification statuses above, timestamp, short evidence statement, limits, and the **same stable saved receipt URL** (e.g., existing `/agent/goals/{id}/view` and job views). Show **"Worker reported complete — verification pending"** where applicable, not a success-colored finished banner. An expander reveals provenance and audit. Verification outages should show the truthful reason and safe next action without prompting the owner to repeat prior approvals. Avoid dumping private memory in evidence panels.

Mobile/iPad layout, screen reader labels, focus retention, reconnection/reload and stale state are Section 01/05 shared acceptance cases. No clickable link should imply remote access works when the service is loopback-only. GET/view/refresh must never schedule a verifier, create consent, or mutate a work item; if automatic verification runs, it must be an explicitly scoped trusted worker event, not an effect of reading a page.

### Example owner-visible result text

> **Mission #18: Source readiness review**  
> Worker reported complete. **Verification: inconclusive.** Local syntax checks passed, but GitHub did not provide a completed run matching the assessed SHA. **Not verified:** current Mac service status, independent runtime success, or code correctness. [Open saved result].

Do not replace "inconclusive" with "failed" when an external service is unavailable. Conversely, a *confirmed exact-SHA failing test* must not be masked as a network problem.

## 7. ATLAS threat and failure register

| Threat/failure | Required fail-closed behavior |
|---|---|
| Worker or model sets `verified=true` in payload | Ignored; only trusted checker may commit verdict after independent observation. |
| Valid SHA/hash on untrusted user-supplied text | Treat as integrity metadata, never provenance or authorization. |
| Green GitHub run for unrelated SHA/workflow or missing required jobs | `inconclusive`; cannot certify candidate. |
| Malicious PR text, fake proof URL, HTML, Markdown or encoded secret | No command execution, no outbound unapproved URL, safely escape and redact text. |
| Verification read runs while candidate changes | Immutable snapshot or detect version shift → `stale`/`inconclusive`. |
| Evidence network outage, timeout, 429/5xx, partial JSON | `inconclusive` with retry eligibility, no arbitrary paid fallback. |
| Contradictory evidence, counterexample, tampered artifact | `failed` when trusted contradiction is definitive; else `inconclusive`; preserve all events. |
| Clock skew, stale timestamps, expired TTL | Not current verified; retain historical proof. |
| Duplicated callbacks or worker restart | Idempotent ledger; one effective verdict per attempt/criterion/version; unknown effects never auto-replay. |
| Interrupted DB transaction or disk-full | No partial verified receipt; durable prior records preserved; explicit attention. |
| Private source/memory content in result | Least privilege, scoped redaction/links, local storage and no public export. |
| Verification code shares mutable data/trust boundary with worker | Cannot claim independent verification without a distinct trusted read-back/observation; label consistency-only. |
| Owner cancelled while verifier runs | Preserve valid previous historical observation but block new claims; do not imply effect was undone. |
| Changed provider/recipient/target or approval revision | Prior verdict cannot be transplanted; new explicit gates and recheck. |

## 8. Exact THRONE work packages and non-overlap rules

**V0 / source reconciliation:** Re-fetch issue #52 newest comment, `main`, PR #58, installed source revision, acceptance register, and prior Section 01 contract. Preserve backups and branch ancestry; do not reinstall or overwrite newer Mac files with stale `main`. Confirm target source and release authority separately.

**V1 / trusted proof collection:** Extend existing health and GitHub read-only *snapshot* paths. Report exact checked source SHA, checked_at, declared check IDs/meaning, fetched CI workflow/run `head_sha` and status. Validate integrity/trust before persistence. Make no private egress or public network binding.

**V2 / durable checker:** Add smallest possible registry of predeclared criteria, scope-specific checkers, append-only verification events, idempotent invocation and safe comparison. Prefer table extension next to existing job/goal evidence, no new task engine. Default legacy data to **not checked** and `independently_verified=false`.

**V3 / receipt projection:** Extend `luna/receipts.py` and `luna/receipt_views.py` to expose worker and verification statuses distinctly with linked evidence and redacted limits, preserving current URL/key contracts. Add goal aggregation with mandatory criterion/all-step semantics. No verification work triggered by GET.

**V4 / test and review:** Implement all `RV-01..RV-44` executable cases from companion CSV with disposable databases, mocked network, fake secrets, source identity mismatch, concurrency/restart, injected content, stale proof, and exact-SHA CI. Focused tests, then trusted full suite and independent source review at final exact head. Existing UI and security protections must not regress.

**V5 / Mac acceptance:** Once THRONE is online, demonstrate actual worker output and a *separate scoped verifier observation* on the real Mac, with saved result surviving service restart, a controlled failure, an inaccessible checker, and source change invalidation. Verify real browser view, local model/provider behavior when relevant, and localhost network binding. Login/boot, off-device backup, mobile pairing and malicious-code sandbox remain separate explicit gates.

**V6 / owner controlled release:** Present observed pass/fail proof, limits and exact source SHA for owner review. Merge, install, publish pojo.3, enable remote/cloud access, spend, delete/migrate data or run generated code **only** with the applicable separate authorization. No broad repeated design audit needed.

## 9. HELM design closeout and reopening criteria

**HELM closeout evidence:** Source-specific findings + normative status/schema definitions + task-type proof requirements + aggregation/privacy/recovery rules + 44-case QA matrix + sanitized sample results + dependency-order THRONE work list. **No** repository edit, passing integrated test, live Mac test, security pen test, owner install/release action or claim of external verification. These are intentionally separate statuses.

**THRONE acceptance:** At the *exact implementation revision*, every applicable RV case has a recorded result/fixture; synthetic passing cases are not mislabeled Mac results; one genuine worker-to-independent-observation-to-saved-result demonstration passes on the Mac; Section 01's MA lifecycle invariants still pass; reviewer confirms least-privilege and no shadow writer; owner separately accepts UI and any sensitive permission changes.

**Reopen design only for:** (1) reproducible behavior violating this written contract; (2) new material security or privacy evidence; (3) platform/API incompatibility that invalidates an assumption; or (4) an explicit owner change of outcome/scope. Record the exact delta and new test. Missing implementation or a failed test is ordinarily an **implementation issue**, not a reason to redo this design.

## 10. Next handoff instruction for THRONE

> **POJO THRONE — Section 02 Result Verification.** Read Section 01 contract and Section 02 contract/matrix, issue #52 and the actual checked PR/main/installed SHAs. Preserve existing durable goals, jobs, receipts, approvals, memory, recovery. Implement task-type trusted evidence collection, verification ledger and truthful receipt labels without duplicating the work queue. Prove `worker complete != independently verified`, exact-commit/workflow CI gating, bounded health scope, proof failures, stale version invalidation, goal aggregation and read-only GET. Run focused negative tests and exact-head trusted suite, then demonstrate real Mac source-scoped verification. Do not interpret green tests as deployment authority. Report observed evidence before requesting separate merge/install/release approval.

**Reference links:** [PR #58](https://github.com/jmann358/Orbit-core/pull/58) · [Issue #52](https://github.com/jmann358/Orbit-core/issues/52) · [receipts.py audited SHA](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/receipts.py) · [app.py audited SHA](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/app.py) · [job tests audited SHA](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/tests/test_mission_receipts.py).
