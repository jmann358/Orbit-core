# ATLAS independent flight acceptance audit — 2026-10-12

**Workstream:** POJO ATLAS (iPad; architecture/QA/independent review). **Status:** independent candidate-source review, NOT owner approval of the Flight Plan, operational certification, implementation authorization, or publication of `docs/FLIGHT_PLAN.md`.

**Stable software baseline:** `main` / published label `pojo.2`, SHA `baf96abff8105b89e7b4c924ff03921f084923b5`.  
**Reviewed candidate:** draft [PR #38](https://github.com/jmann358/Orbit-core/pull/38), `release-candidate/pojo-3-1-0-mac-flight`, HEAD `32d633894b07d59d319d63abb0bd3d1e7c0ff035`.  
**Other overlapping work:** historical draft PR #1 (111 changed paths, conflicting), focused PRs #32–#37 (stacked into #38), and draft financial PR #28. All remain **unmerged** on the inspected date.  
**CI observed:** GitHub `ORBIT checks` at candidate HEAD had successful 3.11/3.13 checks ([run 38284419316](https://github.com/jmann358/Orbit-core/actions/runs/38284419316)); retrieved 3.11 log reports **418 passed, 13 warnings**, and CI checks mark Python 3.13 successful. **No tests were executed on the owner's Chromebook, Mac, iPhone or iPad by ATLAS.**

## Evidence policy

This is a crosswalk to the owner's **unapproved** reviewed Flight Plan 1.0-RC, tests **T01–T34**. The reviewed Plan stays outside GitHub until explicit separate owner authorization. A GitHub CI check or a source test is **candidate evidence**, not a final T-test pass on the required host/device. Inspected source here includes `app.py`, `luna/goals.py`, `luna/goal_recipes.py`, `luna/focus_ui.py`, `luna/approval_center_api.py`, `luna/chat_workflows.py`, `luna/receipts.py`, `luna/worker_heartbeat.py`, the Linux restricted runner, launch guard, and relevant integration/approval tests; this is not a claim to have independently reread every file in PR #38.

Legend: **C** candidate automated evidence (not flight-certified); **P** partial behavior or insufficient test coverage; **B** needs host/device/authority; **M** missing required behavior/evidence in reviewed paths.

| Flight test | ATLAS status | Candidate proof / missing operational evidence |
| --- | --- | --- |
| **T01** natural-language health task creates real IDs | **C/B** | `tests/test_live_server_smoke.py` runs chat→queued job/receipt; repeat or substantiate original host health evidence. |
| **T02** real worker claims and finishes | **C/B** | Spawned Uvicorn/worker test observes saved events; actual owner-host run unverified. |
| **T03** result remains after reload/restart | **C/B** | Live-server process restart and same receipt exercised on CI, not current Chromebook/Mac. |
| **T04** genuine model reply, then recoverable failure | **B** | Provider reliability tests use mocked replies; no actual local-model quality/recovery proof. |
| **T05** specific consent before helper/developer model | **P/B** | `luna/mission_consent.py` and helper gates exist; an approved live model-backed task and denied call evidence still needed. |
| **T06** expired/revoked/provider-changed consent denied, no charged retry | **P** | Requires targeted negative trace at actual request boundary, not only UI approval presence. |
| **T07** useful authorized unprompted issue discovery | **P/B** | Scheduler/autopilot foundations exist; no correlated unprompted owner-host mission acceptance. |
| **T08** bounded plan/delegation/dependencies | **C/P** | `goals.py` fixed allowlist plus `agent_registry`; no general planner or coherent cross-helper mission graph. |
| **T09** authorized continuation without clicks | **C/P** | Two ordered fixed steps run after one API approval in live-server CI; no general adaptive chain. |
| **T10** contextual consent before consequential step | **C/P** | `focus_ui.py` home controls for proposed **fixed** goals; chat-inline, actor/session-bound and sensitive action paths not yet accepted. |
| **T11** approval automatically resumes, later distinct approvals | **C/P** | Fixed goal resumes; no multi-permission live chain or second consequential approval test. |
| **T12** duplicate/stale approvals across two devices | **C/P/B** | Two concurrent `TestClient` requests yield one approval; **not** authenticated-device race, stale version or expired action test. |
| **T13** reject **and modify** | **C/M** | Rejection regression exists. Home `Review or change plan` merely navigates to Goals; no reviewed proposed-goal revision/authorization flow found. |
| **T14** pause/cancel/stop truthfulness | **P/B** | Existing `control_goal` state transitions; actual in-flight side-effects and host stop/restart behavior not evidenced. |
| **T15** bounded retry without duplicate side effects/charges | **P** | Trusted job retry bounds exist; negative proof for non-idempotent external work and charged model calls missing. |
| **T16** truthful no-work idle | **P/B** | Worker heartbeat shows idle; no host-level negative test proving no pointless new jobs from triggers. |
| **T17** safe draft→isolated test→repair→review | **M/B** | Current `restricted_runner.py` is Linux/bwrap, offline CLI only; trusted baseline tests are **not** an untrusted-code sandbox; Mac path unverified. |
| **T18** impossible unauthorized merge/deploy/live apply | **P** | Current workflow intentionally review-only; adversarial negative tests at all application/release boundaries needed. |
| **T19** explicitly approved usable release + rollback | **B** | No owner approval, installation or rollback rehearsal. Keep distinct from a draft PR/green CI. |
| **T20** private memory/backup/restore | **P/B** | Snapshot/integrity defenses and synthetic tests exist; no WAL-consistent recovery of owner's actual state on target host. |
| **T21** Mac launch and interrupted-work recovery | **B** | Mac M4 LaunchAgent/startup/sleep evidence not yet recorded. |
| **T22** delayed chat send/session switch | **B** | Real browser and mobile delayed-response interaction must be tested; unit/HTML checks are insufficient. |
| **T23** secure phone/tablet pair/resume/revoke/offline | **M/B** | Current HTTP app is localhost-only without authenticated remote pairing; do **not** expose over LAN/tunnel. |
| **T24** exact-release regression plus host checks | **C/B** | Candidate SHA CI green; no approved release SHA or corresponding host verification. |
| **T25** no needless duplicate architecture | **P** | Existing SQLite/jobs/goal APIs reused. Full semantic overlap with PR #1 and remaining legacy PRs still needs review. |
| **T26** result link works with appropriate access | **C/P/B** | `/agent/goals/{id}/receipt` and job counterpart return durable JSON, not yet a polished mobile result panel or remotely access-controlled artifact. |
| **T27** legacy PR #1 source provenance | **P** | 111-path inventory and category triage done; path presence is not semantic code equivalence; conflict and failing legacy test remain. |
| **T28** runner OS isolation/fail-closed | **M/B** | Linux runner exists but actual hostile-code host isolation, leak/network/write denial and Mac implementation not verified. |
| **T29** bounded repair reuse/supersession | **M** | Legacy `repair_orchestrator.py` needs security and current-architecture review; no end-to-end bounded repair receipts. |
| **T30** sensitive intake before persistence/upload | **M** | No verified enforcement of comprehensive pre-provider sensitive-intake policy; legacy proposal is not current certified service. |
| **T31** distinguish owner-only watchdog/vault contracts | **P** | Documents correctly distinguish legacy contract schemas from real separate-OS services; actual protected boundaries absent. |
| **T32** one authentic Chromebook→Mac state + rollback | **B** | No approved transfer, integrity-checked Mac restore, or one-writer cutover; recovery text is not a SQLite backup. |
| **T33** $0 / no silent provider bill, unknown cost denied | **P/B** | Fixed goal handlers have no model spending; money-aware metering/unknown-cost denial not verified for broader autonomous APIs. |
| **T34** manual ChatGPT/Codex relay and portable context truthfulness | **P** | Repo documents correctly say bridge is user-mediated and context export is not live backup; require actual per-task receipts before calling it autonomous collaboration. |

## Independent discrepancies requiring HELM disposition

1. **[UX / T13 / F3] "Review or change plan" promises an editor not present in the inspected flow.** In `luna/focus_ui.py`, it calls `selectTab('goals')`. The inspected `app.py` goal endpoints create, decide, report, pause/resume/cancel, but do not revise the exact pending plan. Recommendation: use an honest label immediately, then design explicit `Modify` as a new pending immutable revision with fresh approval and stale-card rejection. Do not edit approved immutable steps in place.
2. **[UX / T10–T11 / F3] Current fixed-goal consent is on the home card/Approvals tab, not embedded in the active chat mission.** The page polls goals only when home is visible, and offers no second permission-specific inline sequence. Recommendation: reuse the current decision/receipt APIs and add one nonblocking contextual card component; do not add another approval datastore.
3. **[Evidence / T12] A two-thread request race proves one SQLite decision, not a secure two-device owner-authority boundary.** In `tests/test_inline_goal_approval.py` both requests use local unauthenticated `TestClient`. Before network use add actor/session and immutable action version/expiry, origin/CSRF protections, device revocation, and negative race tests.
4. **[Result quality / T26] Result URLs currently return bare read-only JSON.** That is a genuine saved result, but not proof the normal owner can easily inspect, understand, and navigate to an outcome on iPhone. Provide a human-readable receipt with objective, measured outcome, source, timeline, failure/uncertainty, child links and technical details on demand; keep the JSON API for machines.
5. **[Review / F0 / T27–T31] Legacy PR #1 is not a drop-in fix.** The remote-build audit mapped filename presence (23 on main, 88 absent from main) but not all high-risk runner/repair/watchdog/sensitivity semantics. Do small high-priority provenance reviews with current file hashes; never mass-merge.
6. **[Proof / F1a, F4–F7] Green CI is not secure code execution, Mac deployment, model availability, remote pairing or owner release approval.** F5 backup/rollback and permission safeguards are prerequisites **before** any F4 live application, regardless of numbered phase order.

## Prioritized, non-overlapping handoff

- **HELM (integration):** keep PR #38 draft; verify new final head+CI after any edits; decide whether to incorporate ATLAS's doc findings and authorize focused repairs; review sensitive action gates before proposing merges. Do not publish `docs/FLIGHT_PLAN.md` absent explicit separate authorization.
- **ATLAS (follow-up only):** independently design and test the **UI/approval state machine** against T10–T14/T26 without editing HELM's `app.py`, `luna/focus_ui.py`, or release candidate in parallel. The companion document in this ATLAS branch is review-only.
- **ENGINE (real host):** short targeted current-Chromebook verification first; no duplicate services or destructive migration; Mac check when physically available. Host logs and counts must use synthetic/redacted output.
- **Owner-only gates:** approve final Flight Plan document and separate publication if desired; separately approve merge/release, Mac migration, runtime sensitive permissions, paid providers and network exposure.

**Safety constraints:** baseline retention C (preserve private histories/backups); Mac-primary uptime B; $0 discretionary spending; public GitHub is only for sanitized engineering documentation. No auto-merge, deployment, release label update, real-data upload, network opening or provider call was authorized or performed by this audit.
