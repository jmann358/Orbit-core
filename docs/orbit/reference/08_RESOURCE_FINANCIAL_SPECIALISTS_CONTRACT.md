# POJO HELM → THRONE | Section 08: Resources, Specialists, Financial Value and Future Experience

**Status: DESIGN READY for phased, bounded expansion; NO paid model, financial pilot, specialist tool account, voice provider, financial account or outside connector is authorized.** Baseline PR #58 `560419de5f21102c9c9995de57dd4bb8890837f9`, October 13 2026. Tests: `08_RESOURCES_FINANCE_TEST_MATRIX.csv`.

## 1. Product priorities without premature execution

Luna should generate practical value: stable local assistance, then useful projects and carefully approved revenue experiments. But new products, earning claims, credit consumption and uncontrolled agents must not preempt dependable missions. In the near term the metric is **verified useful tasks per authorized resource unit**, not marketing claims or number of agents created.

Source reuse: [`luna/model_usage.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/model_usage.py) records provider-supplied token usage but explicitly sets `dollar_cost=None`; **usage accounting is not pre-call billing authorization**. [`luna/agent_registry.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/agent_registry.py) provides static capability labels, **not independent scoped agent identities**. [`luna/proactive.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/proactive.py) previews local attention items and performs no automatic notifications. The prior financial directive is represented by historical PR #28 and the reconciled `docs/FLIGHT_PLAN.md`, not evidence of a funded or operating business.

## 2. Hard resource and monetary contract

1. **Initial $0 discretionary budget:** any unknown-cost, potentially billable cloud request must be denied before dispatch. No card insertion, paid API, auto-upgrade, trial-to-paid plan, unbounded retry or price-unknown provider fallback without explicit owner approval. Local CPU is not literally zero cost; show electric/hardware estimates separately as *estimates*, not billed amounts.
2. **Preflight reservation:** for future authorized paid mode only, atomically reserve request-level maximum charge using verified current provider/model price and bounded maximum input/output tokens. Reject price unknown, budget insufficient, concurrency conflict or unknown retries. Reconcile actual provider billing later. A posthoc token ledger or call count is insufficient.
3. **Model routing:** prefer deterministic cached/tool paths then acceptable local model; only route to cloud with exact approved provider, data class, purpose and hard budget. Never include private memory on provider switch merely because the new model works. Track source and consent in results.
4. **Cancellation and spending:** in-flight charges may still settle; label uncertain charges, enforce upper bounds, do not automatically retry billable calls. Usage and invoices remain distinct. Report unknown cost as `unknown`, never silently $0.
5. **Resource safety:** impose per-task and per-day time/model/CPU/disk limits, concurrency caps and attention limits. Estimate result utility and compare to verified task completion, not model-generated self-rating. Fail closed on unknown provider, missing local model or exhausted quota.

## 3. Scoped specialist/connector contract

6. Begin with a single useful **read-only** specialist task selected by measurable owner value (e.g., repository status inspection). Each specialist gets its own task-scoped identity, allowed tool names, time budget and context subset. Static registry names alone cannot access owner data, network or files. Deny cross-agent credential/memory escalation.
7. Capability grants have IDs, issuer, purpose, subject, resource, permitted action, expiry, limit and revocation; check server-side at every effect. All handoffs preserve traceable provenance and return a bounded receipt to the original mission. Approval from one role cannot create a more privileged role.
8. A connector appears 'connected' only after real authorized account handshake and a successful permitted operation. Revocation must block queued as well as new requests. Distinguish read, draft and **send/mutate** scopes. Credentials stay in owner-controlled secret storage, not model prompts or source control.
9. No automatic external message, outreach, posting, marketplace listing, purchase, contract signature, transfers, or financial account access without that action's exact owner authorization. Nothing from HELM authorizes a connector.
10. Notifications, when later enabled, must be opt-in, deduped, have meaningful-change criteria and quiet hours. Delivery failure is visible; notifications are not equivalent to task completion. Existing suggestion preview alone is not a notifier.

## 4. Financial intelligence and first useful pilot

11. Separate records: **opportunity estimate**, evidence/source timestamp, costs/risk, proposed action, owner permission, actual work delivered, actual revenue/expense, and verified net outcome. An estimate is never called income; a proposed sale is not money earned.
12. Local read-only opportunity research may precede any account connection or outreach, using public data and cited sources. The first pilot should be a **small, specific, lawful, low-cost service** that Luna can materially help deliver with real evidence, not a promise of passive earnings. Do not select a customer/acquisition channel or commit funds in a generic planning contract.
13. Owner chooses the concrete pilot, scope, budget, communications authorization, customer relationship and payout/account mechanisms *when a reviewable proposal exists*. Until then all money movement, binding promises and public offers remain blocked.
14. Build a dashboard showing opportunity statuses, spending approvals, projected versus actual economics, weekly work/report, monthly review and explicit stop-loss decisions. Missing real-world evidence shows 'unverified'. Separate simulated/synthetic financial rows from actuals.
15. If a pilot fails or no lawful feasible opportunity exists, Luna may recommend stopping; never self-justify doubling down or spending more to reach a symbolic income goal. Any resulting tax, insurance, consumer-protection or platform rules need appropriate human review before launch.

## 5. Long-term voice, personality and interface (preserve without blocking first autonomy)

16. Expressive ghost-like identity, optional voice and avatar belong to a **later product track**. Identity/personality preferences remain model-independent and owner editable, with text and accessible navigation always available. No arbitrary visual redesign that breaks missions or mobile approval.
17. Voice starts with explicit push-to-talk, visible listening indicator, recording lifecycle and opt-in provider/cost. No default always-on microphone, hidden speaker detection or unnoticed cloud transcription. Handle barge-in/interruptions without launching unauthorized actions from partial speech. Separate ASR transcript, model response and spoken rendition so user can inspect decisions.
18. Measure CPU, battery, accessibility, background network traffic, warm response time and usability on real THRONE/iPhone/iPad before enabling animations or persistent voice. Provide reduced-motion and text-only fallback. Personality changes cannot change permission/financial/security controls.

## 6. THRONE work packages and closure

**F08-A (P0):** Complete local + cloud *pre-dispatch* budget gate with unknown-cost denial, exact provider consent and atomic quota use in synthetic tests. Never auto-enable a paid provider. Link to Section 03 egress policy and Section 06 cloud standby restrictions.

**F08-B (P1):** Demonstrate one scoped, read-only specialist with real provenance and revocation, not a decorative label. Introduce connector integrations only when selected and owner authorized; record true connected states.

**F08-C (P1):** Build read-only opportunity ledger and pilot selection rubric with source/estimate/actual distinctions. Owner later approves or rejects one concrete pilot. Implement reports and truthful outcomes; no money movement or unauthorized outreach.

**F08-D (P2):** Keep mobile-first interface and accessibility tests alongside Section 05; later preview and obtain explicit voice/identity preferences on examples. Record those decisions once; no questionnaire now that delays P0 autonomy.

**Exit:** source tests pass for budget denial and agent permissions; later real provider/connector/pilot acceptance requires separately approved costs/data/scopes and exact economic proof. Future voice is a **planned extension, not a blocker for the first autonomous mission**. Neither a financial dashboard nor an expressive avatar proves autonomy.

Mapped gates: T05/T06/T08/T15/T16/T33/T34, V01–V10/V17/V18. Dependencies: 01–03, 05 for remote, 06 for standby, 07 for executable specialists. Reopen only when concrete pilot/provider/device acceptance reveals a new requirement.
