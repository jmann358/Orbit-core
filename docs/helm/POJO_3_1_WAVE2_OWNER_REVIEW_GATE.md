# POJO HELM — Wave 2 consolidated owner-review gate

**Status:** DRAFT / REVIEW ONLY. This document is a release-control artifact, not the owner's Flight Plan signoff, source of runtime authorization, or proof of actual product readiness.

## Why this branch exists

The current flight work was spread over two stacked draft pull requests. For the next **owner review**, this branch shows the cumulative changes **from published `main` through #38 and HELM #45 in one comparison** without merging either branch, replacing the live installation, publishing `pojo.3`, or touching a personal database.

| Layer | Exact verified revision at creation | Meaning |
| --- | --- | --- |
| Published `main` / pojo.2 | `baf96abff8105b89e7b4c924ff03921f084923b5` | Owner's unchanged published software |
| First-flight engineering / draft #38 | `32d633894b07d59d319d63abb0bd3d1e7c0ff035` | Fixed safe work steps, real persisted receipts, scheduler and heartbeat foundations |
| HELM refinements / draft #45 | `72365aec53c63c41aa9cbe32453a498150cd191a` | Heartbeat future-clock safeguard, human-readable inert results, chat contextual fixed-plan decision, SQLite backup-handle closure |
| This owner-review branch | Forked **exactly** from #45 | Cumulative review view; release-control document added; no changes to product code |

GitHub's compare of `main` to #45 showed **48 commits ahead, zero behind and 37 changed paths** before this review document. This count describes the *review diff*, not a measure of finished product functionality. PRs #32–#37 and #40/#42/#43/#44 are overlapping, stacked or source-level review units; **do not merge each one independently in addition to this candidate.** PR #1 remains conflicted/CI-failing and must never be wholesale imported. Draft financial PR #28 is independently gated.

## Evidence on immutable source revision

1. HELM #45 commit `72365aec53c63c41aa9cbe32453a498150cd191a` passed two independent full GitHub Actions runs:
   - [38288562196](https://github.com/jmann358/Orbit-core/actions/runs/38288562196): 429 passed, 13 warnings under **Python 3.11**, and 429 passed, 13 warnings under **Python 3.13**.
   - [38288610046](https://github.com/jmann358/Orbit-core/actions/runs/38288610046): 429 passed, 13 warnings under **Python 3.11**, and 429 passed, 13 warnings under **Python 3.13**.
2. At the start of HELM Wave 2, all four checks on the above commit were **completed/success**. The current *owner-review* branch includes an additional documentation commit: verify its **own exact head** and CI before any further proposal.
3. Candidate CI covers a real localhost Uvicorn worker/test-process restart and fixed approved multistep mission, with synthetic/disposable SQLite and no real inference or human Mac/mobile interaction. This is stronger than static mocks in those cases but still **not** evidence of a running self-sufficient Luna on the owner’s Mac.
4. ATLAS's existing draft #41 evaluated earlier PR #38 only. An independent review of **all of #45's additions** is still missing at this document's creation; do not imply another device has approved this code. Source review and UI touch acceptance are different milestones.
5. The source-of-truth contract for this program is `AGENTS.md`, `DEVELOPMENT_POLICY.md`, `docs/POJO_3_1_0_THREE_STATION_FLIGHT_OPERATIONS.md` and recorded owner decisions. This document does not override any of them.

## Next exact work by station (do not duplicate)

### ATLAS — second independent security, QA, acceptance review

- Review **the actual #45 diff against #38**, including `luna/chat_mission_ui.py`, `luna/receipt_views.py`, `luna/database_backup.py`, `luna/worker_heartbeat.py`, `app.py`, `luna/focus_ui.py`, and all changed tests. Record any P0/P1/P2 issue with file/line and a reproducible scenario.
- Extend crosswalk T01–T34 from #41 to the cumulative review candidate and clearly distinguish implementation, automated CI, untested real devices, and owner-only authorization.
- Check stale approval/replay, expired/revoked model consent, denial before paid calls, untrusted receipt text, remote exposure barriers, unavailable real plan modification, and legacy runner/repair/sensitivity risks. Use non-overlapping new tests/docs on ATLAS's separate branch; no edits to HELM integration or ENGINE launcher source.
- Publish a review-only GO/NO-GO assessment and link the exact commit reviewed. **Do not call it flight-certified without required hardware proof.**

### ENGINE — Mac readiness and restoration (no overloaded Chromebook processing)

- Independently review existing Mac `--check` and service `--status` paths plus launch/readiness failure handling. Add focused synthetic tests and repairs only on a separate branch for proven defects. No competing launcher or memory store.
- Produce read-only, first-session Mac M4 mini diagnostics and proper **actual model reply** criteria. Discovery of an Ollama binary or model tag does not establish usable inference.
- Prepare a synthetic WAL-consistent database migration/restore rehearsal and rollback contract. Do **not** access, copy, publish or overwrite owner data while the owner is away.
- Keep Chromebook service/CPU load unchanged; use GitHub Actions for test suites and do not start Ollama, Luna, duplicate workers or local full tests.

### HELM — integration and explicit owner decisions

- Monitor ATLAS/ENGINE branch and PR results, then reconcile only verified, non-conflicting changes into one new **review branch**; source/code review and tests precede decisions.
- Record new revision, cumulative GitHub CI at the exact revision, independent findings/dispositions, and acceptance blockers. No hidden cherry-picks, same-file parallel edits, force-pushes or redundant PR imports.
- Ask the owner one specific question only when reaching an actual approval gate; do other safe independent work first.

## Two different exit definitions

**Stage 1 — One usable supervised Mac Luna (not yet achieved)**

- Mac M4 hardware, Python/runtime/service inspected before installing anything.
- Private source-of-truth SQLite backup recorded, WAL-consistent, integrity verified and recoverable; approved encrypted handoff and **one active authoritative writer**.
- Locally configured AI provider produces a completed **real** answer; failure handling, persistent conversation and independent worker behavior verified after process restart.
- Explicit fixed-goal consent, ordered saved worker receipts, honest state, no unauthorized new privileges, no paid calls, loopback-only HTTP.
- Mac idle/restart/sleep evidence; owner-visible results; clear rollback to original backed-up database and installed pojo.2.

**Stage 2 — Broad self-sufficient Luna (NOT a prerequisite to honestly deliver Stage 1)**

- General permission-aware planner that can safely delegate and resume, with per-sensitive-step immutable approvals, version/expiry/revocation/auditable actor identity.
- Truly isolated Mac-compatible untrusted-code execution, bounded repair/review/revert and strict release gate; trusted `pytest` is not an untrusted code sandbox.
- Approved authentication, encrypted transport, pairing, revocation and offline-resume behavior verified on actual iPhone/iPad before network exposure.
- Real activity/result validation, privacy/intake protections, provider cost denial for unknown-cost calls, reliable service recovery and notification policy.
- The owner can set an authorized bounded goal and receive verified durable outcomes with no silent spending, data loss, release, access expansion or bypass.

## Release/host veto conditions — currently NO-GO for publishing

| Gate | Status now | Verification needed |
| --- | --- | --- |
| Main unchanged and rollback reference | **PASS — source state only** | Recheck before any future action |
| Cumulative code assembled for single review | **PASS — draft only** | New branch CI and ATLAS review |
| Exact cumulative GitHub CI | **PASS on #45 source SHA** | Re-run/inspect exact future owner-review SHA |
| Independent review of #45, UI/approval adversarial cases | **NOT YET** | ATLAS signed findings/disposition; real browser later |
| Genuine M4 model inference + run/restart | **NOT YET** | ENGINE/owner physical Mac proof |
| Actual private SQLite source, backup, transfer, restore and one writer | **NOT AUTHORIZED / NOT YET** | Owner-approved non-destructive transfer plan and integrity checks |
| Secure sandbox and broad autonomous self-development | **NOT YET** | Separate focused security/OS testing |
| Authenticated owner mobile pairing and revocation | **NOT YET** | Separate owner-approved design and physical-device test |
| Owner approval to merge/release/install/migrate or publish Flight Plan | **NOT GRANTED** | Specific, separate decisions at their respective gates |

**Do not publish a release because source-only CI is green.** The owner-approved `docs/FLIGHT_PLAN.md` publication remains separate and unperformed. Discretionary spending is **$0**, retained histories/backups stay intact (retention C), and only one authoritative private memory writer is permitted.

## Review process

1. Re-fetch HEAD and compare `main...this-branch`; make no assumptions about asynchronous sibling-device progress.
2. Wait for or inspect ATLAS/ENGINE review-only branches once they actually exist.
3. Classify every issue: **security/privacy gate**, **first Mac-flight functional blocker**, **future broader autonomy**, or **mere presentation**; do not silently relabel missing features as tested.
4. Fix high-priority release blockers on independently tested review branches with no parallel edits to same paths; hold product-code merges until owner specifically authorizes.
5. Record exact tests, failure logs, mocked versus real behavior, remaining gate and rollback.
6. If all Stage 1 gates pass and the owner approves the reviewed diff **then** discuss publishing `pojo.3`/installation as separate explicit actions. No automatic step.

## Five-line handoff schema

- **Revision:** published `main` SHA; review PR head SHA and base.
- **Verified:** changed paths, CI runs/results and any actual device proof.
- **Blockers:** failed/untested acceptance gates classified by severity and owner authority.
- **Handoff:** ATLAS QA link, ENGINE host/readiness link, HELM combined PR link.
- **Authorization:** precise owner approvals still required; never infer permission from a codeword, test, or silence.
