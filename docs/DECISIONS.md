## 2026-10-12 — THRONE reconciliation package

Owner directed alignment of old/new plans and retirement of obsolete station
work. The active plan and T01–T34/V01–V18 register now share one baseline.
Historical documents are retained with explicit supersession pointers.
The worker autocommit mismatch was reproduced and repaired in candidate
source; explicit immediate reservations are preserved. Launcher unit tests
are independent of the running owner dashboard. Final Mac verification:
496 passed, 13 warnings, zero skips; compilation and case-safe paths pass.
No merge, release, installed-code change, permission expansion, private-data
transfer, new model call or paid service was performed. See THRONE_STATUS.md.

> **THRONE status supersedes older status claims below.** Read [THRONE_STATUS.md](THRONE_STATUS.md), [FLIGHT_PLAN.md](FLIGHT_PLAN.md) and [PLAN_RECONCILIATION.md](PLAN_RECONCILIATION.md) first. The dated entries below are retained evidence, not a live task list.

> **Current confirmed owner choices (Pojo.3.1.0 checkpoint; October 12, 2026):** Mac M4 mini as primary home; Chromebook as current source-of-user-data until a verified safe migration; iPhone/iPad authenticated clients after owner review. **Uptime B:** Mac primary, optional explicitly approved cloud fallback later. **Retention C:** keep histories and recovery copies; no automated destructive cleanup until separately approved. **Starting spending authority $0** and no paid API requests without explicit authorization. In-context approve/modify/reject and automatic continuation are intended; existing steps remain fixed, allowlisted and owner-approved. The reviewed Flight Plan 1.0-RC is *not yet owner-approved for repository publication*. No blanket permission to merge, deploy, change sensitive access or enable automatic code application is implied by this note. This supersedes outdated "not yet decided" wording later in this historical log without modifying the chronology below.

# Decisions and approvals

## Confirmed
- ORBIT is the ecosystem; Luna is its central assistant.
- Luna's data and identity are independent of the model provider.
- Hybrid local/cloud is the eventual goal, with Mac M4 mini as home base.
- Access from iPhone and iPad is a requirement.
- Personality should be expressive and capable of respectful disagreement.
- Routine operations may be delegated; significant decisions require approval.
- Persistent memory and self-improvement are first-class features.
- Preserve scarce premium tokens; prefer legitimate free resources when effective.
- Start with **GitHub-only Phase A**; do not deploy hosting yet.
- User approved creating initial project files in this repository.

## Approval policy
Ask before major architecture changes, external deployment, account creation, financial commitments, elevated permissions, or enabling automatic core upgrades. Clarify ambiguous responses before proceeding.

## Not yet decided
Specific model providers, authentication scheme, retention policy, and deployment method. Do not infer these choices.

## 2026-10-12 — verified product baseline before more capabilities

**Decision:** Preserve the existing FastAPI dashboard, SQLite state, Luna
modules, and approval/allowlist boundaries. Complete repository-wide inspection
and existing tests before implementation; prioritize ordinary conversations
and persistent approved memory over additional planning or autonomy features.

**Evidence:** All 83 tracked files were inspected at upstream revision
`a5eb41a898c250736d760d13cc412f19442f1158`. The unchanged suite passed
182 tests with 9 warnings in 8.68 seconds using a documented external
test-process event-loop scheduling workaround. See `AUDIT.md` for the timeout
reproduction, dependency provenance, inventory, and limits of this evidence.

**Consequence:** No rewrite, completion percentages, or unverified product
claims. `ROADMAP.md` defines acceptance checks; `PROGRESS.md` records results.

## 2026-10-12 — first change: validate model replies and configuration

**Decision:** Repair the existing response adapter before introducing a new
provider abstraction. Reject null, empty, whitespace, and non-string response
content, and handle malformed URL/port configuration as a readable failure.
Add regression evidence for conversation persistence and subsequent recovery.

**Reason:** Invalid provider content currently can violate SQLite constraints
and fail chat; malformed endpoint configuration can raise before the request
error handler. These prevent ordinary Luna use and can be fixed reversibly
without a new dependency or access change.

**Boundary:** Do not relax endpoint restrictions, activate a provider, spend
money, change memory consent, merge to `main`, or deploy. Explicit response
outcomes and separate adapters follow once the narrow fix is verified.

## 2026-10-12 — coordinate existing work; gate remote access

**Decision:** Inspect and coordinate open PRs #12 (launcher), #3 (diagnostics),
#2 (syntax screening), and #1 (sprint work) before overlapping implementations.
Keep the app local while Mac/iPhone security and deployment choices remain
undecided.

**Consequence:** Future device work starts with a concrete owner-reviewed
authentication, pairing, transport, revocation, and retention design. Existing
readiness reports and permission-policy records are not remote authentication.
Routine authorized source work proceeds on focused branches and PRs; sensitive
actions and merging require the applicable explicit owner approval.

## 2026-10-12 — first implementation verified and submitted

**Outcome:** PR #13 preserves the existing adapters and chat API while rejecting
malformed URL configuration, invalid reply shapes, empty text, and Unicode that
SQLite cannot encode. A later valid reply succeeds; approved memory and chat
history survive provider changes and reopening SQLite in a fresh interpreter.

**Evidence:** 219 local tests passed, including 37 new regressions, with the
documented workspace scheduling adjustment. GitHub CI at implementation commit
`6ea197fbd9f8b6b101fced3522ff7cb8fef10eed` independently passed ordinary
Linux/Python 3.13 compilation and all 219 tests (9 warnings, 5.63 seconds).
See [PR #13](https://github.com/jmann358/Orbit-core/pull/13) and
[CI run 38191640970](https://github.com/jmann358/Orbit-core/actions/runs/38191640970).

**Next:** Verify and fix pending-send/session-switch behavior before expanding
the interface. Live inference, browser usage, Mac installation, and iPhone
access remain unverified. The PR is open; no merge or deployment occurred.
