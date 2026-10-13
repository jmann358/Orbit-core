# POJO HELM → THRONE | Section 06: $0 Cloud Blackout Companion

**Status: DESIGN READY AS A RESTRICTED ARCHITECTURE; no cloud account, service, companion, credentials or data transfer exists.** Owner's newest direction in [issue #52](https://github.com/jmann358/Orbit-core/issues/52#issuecomment-6133567244) requires a free blackout standby while THRONE remains primary. It supersedes the *older* 'permanently sole host, no cloud needed' paragraphs in `docs/FLIGHT_PLAN.md`, `docs/ZERO_COST_CLOUD_READINESS.md` and historical handoffs. Source baseline: PR #58 head `560419de5f21102c9c9995de57dd4bb8890837f9`. Tests: `06_BLACKOUT_STANDBY_TEST_MATRIX.csv`.

## 1. Precisely what is being delivered

**Phase C0:** no cloud access enabled. THRONE remains the sole authoritative memory writer. HELM/THRONE can prepare synthetic packets and supported-provider comparison without account creation.

**Phase C1 (first approved delivery):** an authenticated, hard-zero-cost/quota-aware **separate continuity inbox** that may display the last explicitly approved, sanitized operational snapshot and accept a bounded, separately authenticated *owner-authored* note while THRONE is unreachable. An inbox entry is a proposal, not an executed Luna task. No automatic taking over, no shared live SQLite, no private bulk-history copy.

**Phase C2 (later, separately gated):** optional local recovery after reconnection, limited read-only model assistance if its disclosure/cost caps are provably enforced. Automatic failover of writes is **out of scope** until a tested lease/fencing protocol and conflict reconciliation; default remains manually reviewed import.

No vendor can guarantee free hosting, unlimited uptime or quota availability. An unavailable or over-quota free service must show 'standby unavailable', not silently invoke a paid alternative.

## 2. Security and split-brain contract

1. **Authoritative writer:** THRONE is writer A and keeps local database/approved memory private. Cloud maintains a physically separate **append-only, nonauthoritative inbox** of minimal synthetic or explicitly approved payloads. A network outage never implicitly transfers writer authority.
2. **Data minimization:** default allowed replicated context is a sanitized machine status: source SHA, intended plan ID/summary, sanitized acceptance state, snapshot time/TTL, next owner decision, availability flag. No full chat histories, approved personal memory, private SQLite, credentials, raw prompts, private receipts, full source path or unique fingerprint unless separately and specifically authorized under Section 03.
3. **Trustworthy origin:** a signed/authenticated per-message envelope with schema version, producer identity, unique UUID, monotonically increasing sequence or version, issued/expiry time, payload class, source revision and integrity signature. Reject tampering, replay, malformed envelopes, oversized messages, wrong producer, stale TTL and impossible chronology. The cloud never chooses what to declassify.
4. **Explicit consent:** approval identifies *exact fields and destination*, not blanket 'cloud consent'. Changing provider, data class or retention requires new consent. Revoke access and stop future sync; disclose that remote deletion/replication limits depend on the service and must be verified before use.
5. **No paid surprises:** `$0` discretionary cap is a **pre-request deny gate** for nonfree/unknown billing; local token estimates or call-count limits do not prove monetary safety. No credit card required to start first phase. Free quota exhausted/ambiguous means fail closed; don't attempt another vendor or paid tier automatically. Log price unknown as unknown, not $0.
6. **No automatic dual execution:** cloud may queue a proposed instruction for owner review; it cannot dispatch a worker, approve code/memory, deploy, move money, send external messages or access owner credentials. Cloud replies are untrusted external content.
7. **Recovery reconciliation:** after THRONE returns, a server-side operator reconciles inbox items by ID, explicit owner validation, original age/authority, idempotency key and latest local state. Expired, duplicate or conflicting items move to review or rejection, **not replay**. Source-only status heartbeats cannot determine sole-writer safety.
8. **Outage detection:** cloud 'can't reach Mac' is not proof Mac is off; could be local Wi-Fi/VPN failure. Expose uncertainty, distinguish probe stale from proven offline, and never trigger new writer authority solely on missed heartbeats.
9. **Retention C:** preserve owner data and auditable receipts locally; remote standby retains only an approved minimal package for a stated lifespan with service-supported deletion and export. No silently permanent remote retention. If service lacks enforceable deletion, reject that service for personal data; only public/synthetic content may be allowed.
10. **Isolation:** compromised cloud account must not be able to read Mac secrets or command THRONE, elevate local grants, create Github merges, or change local inference endpoint. Import path validates/authenticates messages as untrusted inputs.

## 3. Provider comparison gate (no provider selected)

THRONE must document an actual currently supported free provider before requesting owner authorization, including: verified no-card/no-billing default; usable recurring quota; session/auth/MFA support; data retention/deletion; encryption in transit/at rest; API rate limits; signed messages and audit; graceful expiry; import/export and vendor exit; limits on service uptime; real costs when exhausted. Propose alternate **owner-controlled encrypted static handoff file** if no safe free companion satisfies requirements. No claims of guaranteed always-on service.

## 4. Implementation steps

**C06-A (P0 synthetic):** Define schemas `StatusSnapshot` and `InboxProposal`; bind records to producer, revision, nonce, field-level privacy classes, TTL and maximum bytes. Write rejection tests before transport. Keep a local pure-function reference with synthetic payloads. Source anchors: [`luna/cloud_worker.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/cloud_worker.py) already handles durable leases on *local* SQLite; it is **not a deployed cloud standby**. [`luna/continuity_settings.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/continuity_settings.py) only governs historical chat snippets, not all current chat/provider exposure. Use Section 03 full pre-egress gate.

**C06-B (P0 synthetic):** Build conflict/fencing simulator with Mac online/offline/partition/recovered states, duplicate replay, divergent orders, expired approval and import cancellation. In every scenario cloud writer permission remains false.

**C06-C (owner security decision):** Choose free service with exact scopes and approve account creation/egress only once its hard deny, revocation and deletion are demonstrated on fake data. Account/login actions are not implied by this design.

**C06-D (P1 live, separately authorized):** Deploy minimal provider companion, test synthetic heartbeat + typed owner note, forced outage, quota exhaustion, revoked credential, stale packet and reconciled return. Use real personal material only after separate explicit selection and privacy proof. No two writers.

## 5. Design exit and launch gate

Complete design means we have a safe bounded continuity mechanism and all fail-closed behaviors specified. Actual acceptance requires owner-selected provider, no-spend guard proven with provider account settings, real transport, security test, privacy consent, outage exercise, stale-sync reconciliation, and documented revocation/export. Missing provider remains a **genuine implementation-time decision** rather than a reason to redesign the entire contract.

Mapped gates: T06/T12/T15/T20/T23/T30/T32/T33/T34, V01/V02/V05/V13/V18. Reopen only on conflicting provider/platform facts, failed fencing test or owner change; cloud service cannot quietly become primary.
