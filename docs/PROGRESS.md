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

## 2026-10-14 — PR #74 per-job escalation evidence

Against PR head `5dc00cb20971be6a1836386ae222f969157866d6`, three new
regression cases failed: two pending jobs were marked sent against unrelated
request evidence, and acknowledged/dismissed requests were recreated after a
failed delivery-marker write. The fix opts escalation requests into exact
kind/title/context deduplication across all statuses, with a serialized lookup
and insert. The existing general request deduplication remains unchanged.

Verification in a disposable clone with Python 3.15: focused suite 21 passed;
full suite 532 passed, 6 skipped, 13 warnings (35.71 s); compileall passed.
The three new cases pass. Tests use disposable databases and injected SQLite
failures; this is draft-source evidence, not installed-host verification.
Pending events after manual retry remain gated by current job state and are
not reconciled by this change. No merge or deployment performed.
