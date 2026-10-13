# POJO HELM → THRONE | Credit & Model Intelligence Broker

**Design addendum to Section 08, not a replacement for the established Flight Plan or financial directive.** Reviewed 2026-10-13. Baseline: ORBIT `jmann358/Orbit-core` draft PR #58 at `560419de5f21102c9c9995de57dd4bb8890837f9`. Status **design ready + offline policy prototype tested**, but **no production code changes, no real account discovery, and no provider credentials or usage verified**.

## Owner objective (settled)

Luna should discover legitimate, available AI service allocations, accurately track per-provider rate limits, quota resets, real expiring grants, and charged/free usage; allocate work to the most suitable tool/model, avoid wasting scarce paid or durable credits, and continue work after one provider becomes unavailable. Do not burn credits merely because they exist. Cap all incidental costs at **$0** until the owner separately authorizes a budget. A switch must not disclose unapproved memory, expand task authority, or fabricate continuity.

## Three distinct capabilities

1. **Entitlement discovery**: identify providers and current public trial/free rules through official provider docs; inspect **only linked, owner-authorized account balances** via a supported usage endpoint or owner-supplied record. Label limits as `confirmed`, `reported`, `estimated`, or `unknown` with time/provenance. Do not auto-register accounts, create synthetic identities, rotate keys to evade limits, harvest referral rewards, scrape signed-in consoles, or treat consumer subscriptions as API budgets.
2. **Task-aware execution planning**: classify the request (simple formatting, high-stakes coding, search/retrieval, creative generation, structured extraction, summarization). Combine tools when sensible: web search for evidence, then a language model for reasoning. A search tool is not a substitute for model inference, and model inference is not automatically factual search.
3. **Provider-independent continuity**: persist validated *task state* before dispatch and after every completed step; on 429/exhaustion/expiry, re-evaluate providers and resume only from approved, minimum-necessary facts. Internal hidden reasoning cannot be moved between models; preserve finished actions, decisions, sources, constraints, pending work, and actual output artifacts instead.

## Absolute gates (P0)

- **Privacy**: default local-only for personal/secret content; cloud context requires an exact scoped owner grant listing provider(s), model families, purpose, data class, retention/disclosure expectations and expiration. Existing `continuity_cloud_enabled` controls *older retrieval excerpts*; it does not independently authorize moving the current prompt or approved memory. Never reuse an old Gemini grant to call Groq, or use provider change to lift a deny.
- **Billing**: providers are eligible for unattended free use only when the account/allocation is confirmed free and a **real hard stop prevents overage**. Dashboard spend alerts are not hard stops. Unknown price, balance, conversion ratio, expiration, subscription linkage or billing exposure means **deny** pending explicit authorization. Paid routing requires a new owner-approved risk budget and atomic **maximum-cost** reservation. No surprise credit purchases, card linking, upgrades or hidden retries.
- **Usage units remain separate**: an OpenRouter request allowance, Groq TPM/RPD, Gemini project quota, Cloudflare neurons, prepaid currency, and local inference time cannot be summed or transferred. Each adapter supplies a verified maximum quote in that resource's native unit; the broker rejects unit mismatch or unknown quote.
- **Quality**: never spend credits on a model that fails the task's minimum validated benchmark, context size, modality, tool requirements or structured-output needs. Known lower quality is not compensated by imminent expiry. Validate capability against repeatable synthetic test prompts; record score revision, dates and limitations.
- **Task effects**: automatic failover is safe by default only for idempotent inference or pure read-only work. Do not replay email, a GitHub write, payment or other external effect when the prior outcome is uncertain. Reconcile effect receipt first, then request approval if necessary.
- **Provider refusal/safety**: a provider safety refusal is not a quota failure; do not automatically route elsewhere to bypass the refusal.

## Durable SQLite records THRONE should implement on the sole Mac writer

- `provider_registry(provider_id, endpoint_allowlist_id, adapter_kind, active, privacy_terms_reviewed_at, owner_grant_id, tool_capabilities, created_at)`; secrets referenced by opaque macOS Keychain entry IDs, never stored in logs or the DB.
- `allocation(bucket_id, provider_id, model_or_project_scope, allocation_type, native_unit, confirmed_remaining, reserved_units, nonbankable_reset_at, hard_expiration_at, overage_hard_stopped, observed_at, confirmation_source, confidence, effective_terms_revision)`.
- `model_capability(model_revision, tasks, context_max, modalities, structured_output_support, benchmark_revision, measured_quality, measured_latency, privacy_class_limit)`.
- `job_budget(job_id, allowed_providers, max_per_request_units_by_bucket, max_requests_by_provider, expires_at, data_class, purpose, explicit_owner_revision)`.
- `dispatch_reservation(idempotency_key, job_id, provider, bucket_id, max_units, state, claimed_at, reconciliation_state)`. SQLite `BEGIN IMMEDIATE` must enforce concurrency and idempotency. Reserve BEFORE API request, settle AFTER trusted usage/balance evidence, and mark unknown/ambiguous outcome for review instead of assuming 0.
- `mission_checkpoint(mission_id, version, task_goal, approved_scope_hash, completed_artifact_refs, source_evidence_refs, pending_step, consent_revision, data_class, created_at)`. Checkpoint minimal and encrypted at rest; load/verify checksum or signature, expiry and consent revision before making a new provider call.

No second SQLite writer is permitted. Any future cloud blackout companion gets a scoped isolated inbox and public/approved continuity packet only, not live authoritative database or private memories.

## Selection algorithm

1. Find deterministic or cached tools that can satisfy the task with verifiable output. Search results are grounded with citations and access licensing; structured extraction may require no LLM.
2. Filter local and connected API providers by account connection, current terms, permitted action, network/privacy grant, data classification, safety suitability, context fit and measured task competency.
3. Check per-provider native quota, concurrent reservations, remaining buffer, reset and expiration. Reject unconfirmed/old balances, unsupported models, unknown costs, and anything with possible paid overage when budget=0.
4. Rank eligible models by **validated task success**, then latency and scarce/expiring resource economics. Small expiration bonus may break close-quality ties, never override minimum capability or privacy. Preserve long-lived specialist grants for tasks needing them; nonbankable daily free allotments cannot be saved for later days.
5. Reserve exact upper-bound usage atomically and bind to a single authorized provider+model+purpose+data class. Immediately before send, recheck revocation and allowed context.
6. Normalize provider result, store source/model/version, duration, native metering, actual outcome receipt and checkpoint locally. Never record a guessed credit balance as confirmed.
7. On exhaustion, select another **already-authorized** provider for this step; create a redacted checkpoint with goal, constraints, completed facts, artifacts and next action. If no suitable authorized provider exists, pause truthfully, and offer wait-until-reset or a specific new approval (no blind upgrade).

Priority labels: `P0` privacy, hard-billing stop, atomic reservations, permission boundary, checkpoint; `P1` quality benchmarks, usage reconciliation, expiration optimization, adaptive model routing; `P2` historical utility improvement and supplier discovery notifications.

## Error handling semantics

| Outcome | Luna's action |
|---|---|
| 429 + Retry-After | Wait until allowed or choose other approved model with safe checkpoint; respect all quotas and throttle |
| 402 / balance exhausted | Mark bucket unavailable; no automatic paid purchase or fallback to billable tier |
| 401 / 403 | Disable provider and request owner authorization or credential repair; do not leak key or retry repeatedly |
| Timeout before known result | Read-only inference may retry once within bound; side-effect work requires effect reconciliation before any repeat |
| 5xx / degraded service | bounded backoff, health circuit breaker, then eligible alternative |
| Context size exceeded | compact factual state with references, never silently drop owner constraints |
| Provider policy refusal | surface the refusal and stop rather than route to circumvent |
| Model unknown / rate-card unknown / stale balance | fail closed or use verified local alternative |
| New provider requests private context | require new explicit disclosure permission before any egress |

## User-facing credit dashboard

Show a provider table (connected / not connected, allowed tasks, exact quota kind, remaining confirmed units, reset or expiry, privacy tier, current health, source & last checked). Present a plain-English route receipt: why chosen, other candidates excluded, expected native-unit use, actual metered use, whether any external text left THRONE, and fallback decision. No claims that an account is connected or credits exist without authenticated inspection. Default to **zero-dollar mode**, with a separate clearly marked paid authorization workflow if later desired.

## Reuse existing code / avoid parallel work

- `luna/model_connection.py` currently classifies known endpoint hosts but is not a provider inventory or scheduler.
- `luna/model_usage.py` tracks provider-reported tokens after responses and returns unknown dollar cost; it is not an atomic pre-dispatch cost guard.
- `luna/mission_consent.py` binds grants to ONE existing developer mission, endpoint and model, max two attempts within an hour. **Do not bypass this**; add owner-approved multi-provider pool policy with separately scoped grants and execution-time checks.
- `luna/developer_model.py` isolates development prompts from personal memory and is not a general-purpose model router.
- `luna/continuity.py` retrieves bounded source-attributed historical excerpts and is not consent to upload them.
- Existing Section 03 privacy, Section 02 verified receipts, Section 08 resource ledger, and Section 06 standby contracts remain controlling dependencies. This addendum narrows their requirements into a concrete credit broker; do not replace those sections.

## First bounded THRONE implementation package

1. Read this spec and current `docs/ACCEPTANCE_REGISTER.md`, `docs/FLIGHT_PLAN.md`, issue #52 newest comments, and re-fetch live PR #58 HEAD. Do not assume historical SHA remains current.
2. Build *schema and policy selection* with synthetic balances and benchmark fixtures only. Do not contact a live provider, inspect keys, move memory, or activate cloud.
3. Add atomic quota reservation/reconciliation and consent checks against disposable SQLite database; prevent double claims across two concurrent workers.
4. Test one local-only routed task, one simulated free cloud inference, 429→eligible provider switch using approved public checkpoint, 402→pause, unknown-cost denial, and private-memory egress rejection.
5. Only after independent security review and separate owner approval, connect a single legitimate API provider using read-only quota inspection and prove real invoices cannot be triggered by the free-only path.

**Exit**: one test task finishes with the right model, an explained credit allocation, preserved factual context after simulated exhaustion, a verified receipt, no unauthorized outbound transfer, and no surprise charge. Never call the capability production-ready from the 30 synthetic tests in the companion reference.

## Recheck current public documentation before integrating any provider

- Gemini API billing/free tier: https://ai.google.dev/gemini-api/docs/billing
- Gemini API per-model pricing, data use: https://ai.google.dev/gemini-api/docs/pricing
- GroqCloud per-model limits and rate headers: https://console.groq.com/docs/rate-limits
- OpenRouter plan and free-model restrictions: https://openrouter.ai/pricing
- Cloudflare Workers AI current daily free allocation: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Microsoft **legacy Bing Search API retired 2025-08-11**, substitute has distinct billable licensing: https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement

All amounts are provisional *public plan descriptions*, not the owner's actual balance or a promise of free billing. THRONE must check legal API access and actual account state. A consumer subscription (ChatGPT, Copilot, etc.) does not automatically confer programmable API quota.

## Reference prototype limitations

`credit_router_reference.py` is **pure and offline**. It does not connect providers, read credentials, reserve SQLite capacity, enforce multistep workflow effect idempotency, measure quality, or prove provider claims. `test_credit_router_reference.py` contains 30 synthetic selector/checkpoint tests; passing them proves only those reference invariants. THRONE is responsible for all production implementation and security testing.
