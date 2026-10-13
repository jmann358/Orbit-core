## 2026-10-13 — exact test inputs before candidate execution (source review)

Base draft #70: `06dd34ef18cc17c1f48e2c016b3d274aa66ecccf`. The existing proposal
fingerprint binds test names but not test bytes or imported source. A reproduced
case changes a committed test without changing that old fingerprint. The new
read-only preparation packet binds the candidate, selected tests, committed
source blobs, base commit/tree and bounded source inventory to a new digest.
Dirty inputs, uncommitted tests, symlinked inputs, case collisions and oversized
blobs are rejected. Private files and environment files are outside the fixed
inventory. No checkout, dependency install or candidate import/execution occurs.

Agent Studio can save an idempotent durable test-input review against the exact
displayed proposal. The first predefined test selection supports only the
existing diagnostics target `luna/development.py`; other targets stop. Source
finding evidence and mission state are rechecked before saving. A disposable
browser preview inspected a synthetic proposal and saved its review, displaying
its commit, tests and digest plus the explicit unverified runner/approval state.
The preview was stopped afterward; no live Luna or private database was used.

Baseline: 38 relevant tests passed. Final Mac/Python 3.13 suite: **587 passed,
13 warnings, zero skips in 37.78 seconds**. Compilation and diff checks pass.
Nine new cases cover input identity, stale/dirty source, bounds, symlinks and
durable idempotent review. Candidate fixtures are strings only and never run.

This is partial D07-A/C preparation. It is NOT integrated with the existing
Linux runner and does not secure or authorize that execution path. Dependency
image identity, complete environment reproduction, Mac VM isolation and hostile
fixture checks, a real repair/test loop, independent review and live promotion
remain open. Independent encrypted backup/recovery and host setup remain gated;
the owner directs continued source work. The 333-case acceptance ledger remains
NOT_RUN.

## 2026-10-13 — connect a verified finding to bounded drafting (source review)

Base draft #69: `a96af679efefd865de7f0854f2516380708d72b8`. Source review and
developer missions were disconnected: drafting used generic templates without
preserving the observed finding. A new explicit source-review request now accepts
only a fresh, verified syntax finding in an already allowlisted draft target.
It freezes the job/attempt, report and source fingerprints, path, line and narrow
success condition. No finding or a protected target yields no draft.

The existing developer queue/model consent/budget remain authoritative. Repeated
requests for identical evidence return the same mission even after it reaches
review; collisions with other active drafts do not attach or overwrite evidence.
Before model attempts and before accepting a proposal, the evidence is rechecked.
Changed evidence stops at attention. Model prompts receive only the bounded
source finding, never arbitrary job text or private conversations. Source reads
now use the existing pinned no-follow read primitive. Candidate code remains
unexecuted and unapplied; syntax validation is not functional verification.

The saved source-result page links to a review request in Agent Studio, where
the owner explicitly queues the observed repair. A disposable browser check
followed that link, queued one mission and inspected its retained evidence.
No model or startup worker was enabled in the preview; it was stopped afterward.

Baseline: 48 relevant tests passed. Final Mac/Python 3.13 suite: **578 passed,
13 warnings, zero skips in 37.00 seconds**; compilation and diff checks pass.
Seven new cases use synthetic source, SQLite and an injected fake model to prove
evidence-to-candidate persistence, source unchanged, no model call on stale
evidence, mid-call change rejection, collisions, concurrent duplicate requests
and refusal to broaden target scope. These are not live-model or isolated
candidate-execution results.

Read-only host checks observed macOS 27.0.1, Mac16,10, 16 GiB RAM and 10 logical
CPUs. No container/Docker/Podman/Orb executable was on the inspected PATH. The
existing execution runner is Linux-only; no Mac isolation is claimed. An Apple
container evaluation proposal is prepared separately for owner review; no runtime,
image, dependency or service was installed. Independent backup/recovery and
host-change approval remain pending. Partial D07-A/C source progress only:
Mac isolation attacks, real bounded repair/test loop, exact Git tree manifests,
independent review and live promotion remain open.

## 2026-10-13 — evidence-based local development recommendations (source review)

Base: draft #68, `f46e201a38dfc134c5abcfba1beb97a1914d6304`. The existing
development-plan handler returned the same scheduler checklist for every task.
After a 33-test baseline, a new regression reproduced that placeholder behavior.
The handler now observes the existing ten-path source allowlist using bounded
no-follow reads, saves a manifest and prioritized findings, and recommends a
specific next review action. Clean inputs produce no invented defect. Neither
source snippets, private data, model calls nor executable commands enter the
artifact. Artifacts are immutable per job attempt and carry mission revision
and approval digest when applicable.

A separate checker reopens those paths and independently implements the
presence/readability/syntax and priority checks. It does not call the worker's
observer or report builder. Tests demonstrate rejection of a worker fed an old
snapshot, source/result/artifact/binding changes, symlink parents and historical
generic plans. Verification events preserve stale/restored history and deduplicate
concurrent identical observations. This certifies only the named source checks
and deterministic recommendation selection, not complete diagnosis or repair
safety. Content fingerprints are not Git commit SHAs or authentication.

The fixed local-development-review recipe runs health then development planning
without a model or network. Mission receipts expose scoped per-step evidence
and its aggregate; they still do not certify a free-text objective. Criteria
IDs are frozen in new mission plans. Earlier review-build approvals whose
contract lacks these criteria fail integrity checks and require a new proposal;
no historical approval is silently upgraded.

Final Mac/Python 3.13 suite: **571 passed, 13 warnings, zero skips in 36.36
seconds**; compilation and diff checks pass. Thirteen new planning tests cover
actual observations, clean/faulted fixtures, tampering, immutable attempts,
stale/restored evidence, concurrent checks and durable HTTP results. The real
loopback two-step worker test now checks both scoped evidence records and saves
the identical plan artifact across a process restart. Browser inspection of a
disposable completed plan confirms the result, recommendation, scope and evidence
display. The preview was stopped. No live provider or installed Luna was touched.

Partial P0-4 source milestone only. Broader issue discovery, exact-commit external
CI evidence, autonomous patch/test/repair in OS isolation, owner acceptance and
installed recovery remain open. The 333-case acceptance ledger remains NOT_RUN.

## 2026-10-13 — exact mission revisions and inline replacement (source review)

Continuation from draft PR #67 at `9d012c2851492d2b37c423854c9e1ab63a038ed3`.
Reproduced missing displayed-plan preconditions, approval reuse after changing
both a queued job and its step, and cancellation claiming a final result while
a handler was still running. Proposals now freeze their ordered steps, scope,
limits and evidence policy; HTTP decisions require that exact revision/digest.
Jobs retain their originating mission/revision/digest, and claim-time checks
deny changed or orphaned assignments. Hashes are integrity checks, not identity.

Inline modification creates one linked, unapproved successor transactionally.
Queued old work is cancelled; started or restart-interrupted work holds the
replacement for reconciliation. Cancellation remains requested until a started
task settles. Old outcomes and approval events remain in receipts. Legacy
approvals lacking a frozen plan become review-needed instead of gaining newly
invented scope. An interrupted outcome remains uncertain without automatic replay.

Home, Chat and Goals share an inline editor and revision-aware decisions.
Actual browser checks on a disposable localhost server exercised modification,
fresh approval and replacement of an approved revision, reload persistence,
Home/Chat consistency, and a 390-pixel narrow viewport. Browser testing caught
and fixed a newer approved proposal hiding a running mission. The preview had
no model and no active worker; it was stopped after checks. Separately, the
real-loopback worker smoke test completed a revised two-step mission and
preserved its revision, approval and task IDs across process restart.

Final Mac/Python 3.13 trusted suite: **558 passed, 13 warnings, zero skips in
36.32 seconds**. A prior full run found one obsolete terminal-decision assertion
(404 versus the new 409 conflict); it was corrected and the complete suite rerun.
Fourteen focused revision regressions include stale decisions, racing successors,
rollback, legacy migration, orphaned jobs and cross-mission reassignment. Tests
use disposable databases, fake providers and temporary loopback servers.

This is partial P0-3 source work for review, not MA-01..MA-28 acceptance or a
live upgrade. Real device/owner acceptance, interrupted-outcome reconciliation
workflow, full task-specific verification, and broader autonomous/self-development
missions remain open. The 333-case acceptance ledger is unchanged (NOT_RUN).
The owner confirmed backup/recovery remains pending and requested source work.

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

> **Pojo.3.1.0 development progress (2026-10-12; review-only):** The current **draft** flight code carries 418 passing tests and 13 warnings on each of Python 3.11/3.13 at candidate run [38282532948](https://github.com/jmann358/Orbit-core/actions/runs/38282532948), and subsequent branch runs independently check the latest changes. Scenarios now include real loopback Uvicorn, approved two-step goal continuation, saved job/goal receipts, observed worker heartbeat, atomic dispatch and SQLite lifetime. See [complete acceptance evidence](POJO_3_1_0_ACCEPTANCE_EVIDENCE.md) and [Mac handoff](POJO_3_1_0_MAC_HANDOFF.md). These edits are **not merged**, and the real Mac, iPhone and model provider have not been tested. All older test counts in the chronological report below are historical, not current product certification.

> **Integration update (2026-10-11):** The detailed audit below reports an earlier source snapshot, not the latest integrated build. PRs #16–#19 merged with CI evidence; see [master-plan reconciliation](MASTER_PLAN_RECONCILIATION.md). No live provider, Mac M4, iPhone or continuously hosted deployment has been verified.

# Development progress

## 2026-10-13 — result verification recovers honestly and reads bounded source

Follow-up to PR #66, exact base `357f8fca638b82551cdc4e31020de286c5e67d38`.
Two regressions reproduced before repair: a restored source revision stayed
stale forever, and a symlinked parent directory was accepted as in-scope source.
Verification now deduplicates only consecutive identical observations under
the existing SQLite write transaction, preserving verified/stale/verified
history. Legacy review-build events retain their IDs and contents during the
transactional table upgrade. Source reads pin directories and files with
no-follow opens, reject non-regular or oversized files, and bound bytes read.

Seven new regression tests cover those failures plus event preservation,
concurrency, oversized input and source-open races. Final Mac/Python 3.13
suite: **544 passed, 13 warnings, zero skips in 36.57 seconds**. The bundled
Node runtime enabled all six optional JavaScript checks. Initial restricted
run: 534 passed, six skips and four localhost-bind permission failures; rerun
with temporary loopback test servers: 538 passed/six skips; the final complete
run above resolves both environment limitations. Disposable SQLite and fake
provider fixtures only; actual test worker/server restart cases ran. No owner
memory, live Luna update, provider call, generated-code execution or release.

Owner confirms independent backup/recovery is still pending and requests
continued source work. The 333 planned acceptance scenarios are not marked
passed by this suite. P0-2 remains a partial, review-stage deliverable; a full
autonomous development/test/repair/promotion cycle is not yet certified.

## 2026-10-12 — complete audit and tested conversation reliability slice

Audited upstream source: `a5eb41a898c250736d760d13cc412f19442f1158`.
All 83 tracked files were inspected and matched to upstream Git blobs before
implementation. See [AUDIT.md](AUDIT.md) and the
[source/evidence inventory](audit/2026-10-12-inventory.json).

| Work | Verified state |
| --- | --- |
| Repository-wide audit | Complete: application, 36 Luna module files, 26 tests, documentation, dependencies, launcher, CI, and task data reviewed. |
| Existing test baseline | 182 passed, 9 warnings in 8.68 s; exit 0. Requires the external 20 ms event-loop polling workaround documented in the audit. Ordinary invocation timed out after 180 s, including reproduction against a bare FastAPI app. |
| Persistent foundations | Existing tests verify SQLite chat/history, memory review, continuity consent, goals/worker safety, proposal integrity, and backup behavior with disposable data and mocked providers. |
| Provider reliability fix | Implemented: invalid response text, malformed Gemini parts, invalid UTF-8, malformed endpoints/ports, timeouts, invalid JSON, and provider HTTP failures produce bounded notices. Tests verify subsequent successful replies. |
| Conversation and memory integration | Mocked OpenAI-compatible/Gemini replies retain the charter and approved memory; pending memory and other-session text are excluded. A fresh Python interpreter reopens the SQLite file and verifies four saved turns and approved memory. |
| Post-change regression suite | 219 passed: 182 existing cases plus 37 new cases; 0 failures, errors, or skips; 9 deprecation warnings; 13.11 s. Uses the same external scheduling workaround as the baseline. |
| GitHub CI | Normal Linux/Python 3.13 execution passed compilation and all 219 tests with 9 warnings in 5.63 s, without the workspace scheduling workaround. [Run 38191640970](https://github.com/jmann358/Orbit-core/actions/runs/38191640970) tested implementation commit `6ea197fbd9f8b6b101fced3522ff7cb8fef10eed`. |
| Other checks | Python compilation and app import passed; embedded dashboard JavaScript passed `node --check`. Chromium could not launch because socket creation was denied, so there is no browser interaction verification. |
| Test setup and run docs | Added `requirements-dev.txt` with pytest 8.4.2; CI installs that manifest; README/RUN setup uses it; RUN now states Python 3.11+ and 30 recent turns plus approved context/cloud opt-in. Clean installation on Mac remains unverified. |
| Development instructions and records | `AGENTS.md`, audit, prioritized roadmap, this report, inventory, and decision entries established. |
| Branch/PR | [PR #13](https://github.com/jmann358/Orbit-core/pull/13), branch `fix/luna-conversation-reliability`, implementation commit `6ea197fbd9f8b6b101fced3522ff7cb8fef10eed`. Open for review; no merge or deployment performed. |

The baseline is evidence about assertions in the existing suite, not a claim
that Luna is ready for everyday use. No live model, actual browser conversation,
listening server, Mac M4 installation, iPhone connection, or restore rehearsal
was verified. Actual provider access requires configured, approved resources.

The [post-change pytest log](audit/2026-10-12-final-pytest.txt) and
[JUnit results](audit/2026-10-12-final-pytest.xml) retain exact suite evidence.
The final command was:

```bash
PYTHONPATH=/workspace/test-deps/pytest/src:/workspace/test-deps/pluggy/src:/workspace/test-deps/iniconfig/src:/workspace/Orbit-core \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  LUNA_DB_PATH=/workspace/audit-artifacts/final-test-data.db \
  python /workspace/audit-artifacts/run_pytest_with_polling.py -q -p no:cacheprovider tests \
  --junitxml=/workspace/audit-artifacts/final-pytest.xml \
  > /workspace/audit-artifacts/final-pytest.txt 2>&1
```

Run from `/workspace/Orbit-core` with isolated `LUNA_DB_PATH`. The external
entry point/dependency sources belong to this cloud workspace; normal host/CI
verification uses the installed test manifest and `python -m pytest`.
The [entry point is preserved as text](audit/run_pytest_with_polling.py.txt) for
inspection and reproduction. With pytest installed, Python can execute that
text file directly; use it only to investigate the documented environment stall.

## Remaining work

Review PR #13, then verify pending-send/session-switch behavior and
interactive chat. Explicit typed model failures, deterministic connection
closure, atomic backlog dispatch, case-safe Mac checkout, launcher backup, and
restore rehearsal remain on the roadmap. Model failures are still represented
as notice strings in saved history; this fix does not introduce typed outcomes
for all drafting/planning callers. Remote access remains unimplemented.

## Reporting rules

Append dated evidence as work advances. Distinguish source review, automated
tests, mocked adapter tests, local server/browser checks, hardware checks, and
owner approval. A failed or unavailable check remains visible until resolved.
Record exact counts and outcomes; do not invent completion percentages.

## Local drafting acceptance — follow-up

The original proposal path failed strict validation twice against public
`luna/skill_catalog.py` in disposable state. The candidate now requests
schema-constrained output only at the local Ollama-compatible endpoint
(port 11434, /v1). Path and base revision are constrained, and the existing
revision, size and Python-syntax validation still apply. Other providers
retain their previous payload, and rejected requests do not trigger a
less-constrained fallback.

The same local qwen2.5-coder:7b then produced a proposal that reached review
on its first attempt in 30.42 seconds. Source remained unchanged, generated
code was not executed, and private memory was not used. This proves one
local drafting scenario, not correctness of the proposed improvement or
a complete test/repair/deployment cycle. The old production failure remains
a preserved historical record; these fixes are not installed yet.

Full regression: 502 passed, 13 warnings, zero skips in 35.91 seconds.
Transport, consent, rejection, retry and local-only scope tests passed.
Reference: https://docs.ollama.com/capabilities/structured-outputs
