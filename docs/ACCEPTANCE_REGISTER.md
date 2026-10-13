# Luna acceptance register

October 12, 2026 · Companion to FLIGHT_PLAN.md / LUNA-STAGED-PLAN.md · Proposed gates, not newly performed tests

T01–T34 preserve the scope recovered from [ATLAS PR #41](https://github.com/jmann358/Orbit-core/pull/41). Historical status labels were reconciled with the later #57 candidate and THRONE evidence. H = observed on THRONE for the stated narrow scenario; C = candidate source/automated evidence; P = partial; U = unverified or missing. H does not certify every edge case.

| ID | Requirement / observable pass condition | Current evidence and remaining work | Stage |
| --- | --- | --- | --- |
| T01 | Natural-language task produces a real saved job ID | H: health task job 27; extend beyond narrow supported routing | 3 |
| T02 | Worker actually claims and completes work | H: completed health job; broader handlers need acceptance | 3 |
| T03 | Same result survives refresh and restart | H: service restart preserved job/chat; browser and reboot cases remain | 1–3 |
| T04 | Genuine model reply and recovery from failure | H/P: local reply verified; controlled provider-loss/recovery and quality suite pending | 2 |
| T05 | Helper/developer model call has exact valid consent | C/P: controls exist; record real allowed and denied request traces | 3 |
| T06 | Expired, revoked or provider-changed approval blocks calls | C/P: test at execution boundary, including queued work and restart | 3, 6 |
| T07 | Useful unprompted work occurs within approved scope | P: scheduler exists; failed draft is not successful useful delivery | 3 |
| T08 | Bounded plan/delegation respects dependencies | C/P: fixed recipes; broader planner and scoped delegation unfinished | 3, 6 |
| T09 | Authorized steps continue without repeated prompts | C: ordered fixed steps; meaningful broader Mac mission pending | 3 |
| T10 | Consequential approval appears in mission context | C/P: fixed-goal card exists; broader actor/action/scope-bound flow pending | 3 |
| T11 | Approval resumes only the authorized next work | C/P: fixed sequence; distinct second sensitive action needs separate proof | 3 |
| T12 | Duplicate/stale decisions across devices execute once | C/P: local races covered; authenticated device races/expiry pending | 3–4 |
| T13 | Reject or modify creates truthful, safe state | P: rejection and honest label exist; replacement revision/approval needed | 3 |
| T14 | Pause/cancel/stop accurately describe effects | P: states exist; in-flight and uncertain external outcomes need tests | 3 |
| T15 | Retries are bounded and do not duplicate effects/charges | P: limits exist; end-to-end idempotency and uncertain outcome handling pending | 3, 6 |
| T16 | Idle means no manufactured work or spending | P: idle observation exists; negative trigger and resource test pending | 3 |
| T17 | Draft → isolated test → repair → review completes | U: full Mac cycle absent; developer draft failed in setup | 5 |
| T18 | Unauthorized merge, deployment or live apply is denied | C/P: review-only default; adversarial integration tests required | 5 |
| T19 | Approved release installs and can roll back | U: controlled release/promotion and rollback rehearsal pending | 5 |
| T20 | Private memory can be backed up and restored | H/P: transfer/restore verified; ongoing backups and independent medium pending | 1 |
| T21 | Startup and interrupted work recover on Mac | H/P: service restart verified; boot/login, soak and uncertain jobs pending | 1 |
| T22 | Delayed send and session switching preserve correct chat | C/U: automated foundations; full actual-browser interaction matrix pending | 2 |
| T23 | Pair, resume, revoke and reconnect real mobile devices | U: localhost-only app, no authenticated remote access | 4 |
| T24 | Release revision passes regression and host acceptance | C/H: #57 CI and local ee067a3 suite; future release SHA not yet approved | 0, 5 |
| T25 | Existing architecture is reused without duplication | P: inventory available; semantic overlap/disposition still required | 0 |
| T26 | Readable result remains accessible to authorized owner | C/H: readable views implemented, saved result exists; mobile/access QA pending | 3–4 |
| T27 | PR #1 work has a feature-level provenance decision | P: filename inventory exists; retain/adapt/supersede/defer by behavior required | 0, 5 |
| T28 | Hostile generated code cannot escape its sandbox | U: Linux-only CLI runner is not Mac isolation proof | 5 |
| T29 | Repairs reuse safe prior work and stop at the limit | U: legacy orchestrator review and bounded full-cycle evidence pending | 5 |
| T30 | Sensitive intake policy applies before storage/upload | C: #57 handles obvious sensitive patterns; broader privacy limits and tests needed | 2, 6 |
| T31 | Vault/watchdog have real independent access boundaries | U/P: concepts/contracts and disk encryption are not isolated services | 5–6 |
| T32 | One authoritative Chromebook-to-Mac state with recovery | H/P: cutover verified; older source preserved; later Mac changes need own backup | 1 |
| T33 | Zero/unknown budget prevents unapproved provider billing | H/P: current local cloud-disabled configuration; future monetary enforcement missing | 6 |
| T34 | Bridge and portable context claims match actual behavior | P: manual handoff exists; real per-task receipts and recovery dossier needed | 0, 6 |

## Additional master-vision and home-operation gates

| ID | Required result | Stage |
| --- | --- | --- |
| V01 | Personal memory is inaccessible to other agents; technical sharing is explicit and source-linked | 2, 6 |
| V02 | Model change preserves identity/history without implicitly granting a new provider data access | 2, 6 |
| V03 | Corrections, conflicting facts, export, owner deletion and retention rules behave consistently | 2 |
| V04 | One real specialist completes a scoped task; revocation/cancellation and context isolation hold | 6 |
| V05 | Each connector shows actual connected state and scope; revoked credentials cease working | 6 |
| V06 | Notifications obey opt-in, quiet hours, deduplication and meaningful-change rules | 6 |
| V07 | Financial estimates and actual results stay separate; spending and money movement remain denied absent specific authority | 7 |
| V08 | Approved financial pilot records delivery, actual expenses and outcome; failed pilot has a stop decision | 7 |
| V09 | Voice consent, recording lifecycle, interruption, accessibility and text fallback verified | 8 |
| V10 | Personality/appearance choices persist with acceptable measured CPU and mobile usability | 8 |
| V11 | Shutdown/move/home boot/login succeeds; no dependency on the previous Wi-Fi network or Chromebook | 1 |
| V12 | Power-loss recovery accurately discloses login requirement; no claim of uninterrupted operation without power | 1 |
| V13 | Backup/disk/resource failures yield actionable status without deleting protected history | 1 |
| V14 | SQLite implicit rollback and explicit atomic reservation verified in candidate source; deployment remains separate | 0–1 |
| V15 | Local Mac commit is preserved and future update path cannot silently discard its tested fixes | 0, 5 |
| V16 | Historical documents, runtime status and public release label agree on what is installed versus published | 0 |
| V17 | Development assignments have a bounded scope and checkpoint; duplicate agents/audits are not the default | All |
| V18 | A fresh session can resume from the saved plan/evidence without treating a codeword as memory or permission | 0 |

## Evidence template for every future work package

Record: requirement IDs; exact code/proposal revision; fixture/host/device; expected behavior; observed result; failure and rollback evidence; whether provider/worker/transport was mocked; test command or reproducible owner steps; sanitized artifact link; remaining limitations; reviewer and owner decision where required.

Do not mark a requirement passed from an implementation label, HTTP success alone, a model's assertion, a heartbeat, or an unrelated green test suite. An approved deferral is a scope decision, not a passed test. Keep current source, installed source and published release distinct.

## First implementation package — now in progress

**Scope:** preserve/review ee067a3, resolve the cloud-worker transaction finding on synthetic data, reconcile the release/update path, and prepare the exact home boot/login checklist. No model upgrade, integrations, UI redesign, duplicate migration or broad test reruns solely for planning.

**Acceptance:** V14–V16 have reviewable evidence/disposition; T24 identifies one candidate against main; V11 has a safe scheduled owner procedure. Transaction reproduction and repair are complete in the candidate; consult THRONE_STATUS.md for final test and preservation evidence. Continue with the next bounded package after its dependencies pass. The actual move/reboot requires the owner's timing and should not be triggered during this planning discussion.
