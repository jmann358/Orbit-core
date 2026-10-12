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
