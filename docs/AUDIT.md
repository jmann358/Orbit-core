> **THRONE status supersedes older status claims below.** Read [THRONE_STATUS.md](THRONE_STATUS.md), [FLIGHT_PLAN.md](FLIGHT_PLAN.md) and [PLAN_RECONCILIATION.md](PLAN_RECONCILIATION.md) first. The dated entries below are retained evidence, not a live task list.

> **Newer Pojo.3.1.0 candidate evidence (2026-10-12):** The 83-file / 182-test inventory below remains an accurate *historical baseline* at `a5eb41a`, not the current source inventory. Published `main` is still `pojo.2` at `baf96ab` with 380 CI passes per Python version. Current **unmerged candidate** includes actual Uvicorn chat→worker→saved receipt, a two-step approved mission, honest worker heartbeat, safe SQLite handling and diagnostic-only runner check. See [Pojo.3.1.0 acceptance evidence](POJO_3_1_0_ACCEPTANCE_EVIDENCE.md), [Mac handoff](POJO_3_1_0_MAC_HANDOFF.md), and PR #38 for exact source and latest CI. Neither cloud inference nor the owner's Mac/iPhone was verified. Do not interpret green CI as merge/deployment authority.

# Repository audit — 2026-10-12

## Targeted follow-up — 2026-10-13, PR #66 at 357f8fc

The original six source-verification tests and four mission-receipt tests pass.
Two added regressions fail on that exact source: (1) verified -> stale -> source
restored remains stale because permanent event uniqueness discards the new
verified observation; (2) `luna/core.py` is accepted through a symlinked `luna`
directory. Both are repaired in the isolated follow-up. Seven regression cases
cover restoration, old-event preservation, concurrent deduplication, parent and
racing leaf symlinks, oversized input and disappearing source. This scope does
not repeat the historical repository audit or certify the running installation.

The repository has substantial tested local foundations, but a passing unit
suite does not establish a reliable assistant product. The first implementation
priority is the ordinary conversation path and its persisted history and memory,
before adding more autonomy or remote deployment.

## Scope and source baseline

Audited upstream revision:
[`a5eb41a898c250736d760d13cc412f19442f1158`](https://github.com/jmann358/Orbit-core/commit/a5eb41a898c250736d760d13cc412f19442f1158).
The team read all 83 tracked files: 63 Python files, including 26 test files;
the dashboard/API; all Luna modules; both README files; all 12 documentation
files; development policy; requirements; task data; launch script; CI workflow;
and ignore rules. There are 102 declared application routes.

The source was obtained through the connected GitHub account. Every file was
checked against its upstream Git blob hash and byte count before testing.
The workspace's reconstructed Git commit is a local snapshot identifier, not
the upstream commit. [The machine-readable inventory](audit/2026-10-12-inventory.json)
records file hashes, categories, route declarations, and baseline test evidence.
Implementation started only after this repository-wide audit and baseline.

## Existing test results

**182 passed, 9 deprecation warnings, 8.68 seconds.** The process exited 0;
total process elapsed time was 9.34 seconds. Runtime: Python 3.12.14,
pytest 8.4.2, pluggy 1.6.0, iniconfig 2.1.0, FastAPI 0.141.1,
Starlette 1.6.0, HTTPX 0.28.1, AnyIO 4.14.2, and Uvicorn 0.52.1.

An ordinary pytest invocation timed out after 180 seconds at a FastAPI
TestClient request. The same stall was reproduced with a bare FastAPI app.
An external test entry point scheduled a recurring 20 ms asyncio timer to
allow thread-scheduled work to progress. This changed test-process scheduling
only; repository code, assertions, HTTP clients, and network permissions were
unchanged. The result above is conditional on that documented workaround.
It is not evidence that ordinary pytest or a live server works in this cloud
workspace. Warnings concern deprecated FastAPI startup/shutdown handlers and
the installed Starlette TestClient/HTTPX combination.

Pytest was initially unavailable. Authentic upstream release sources for
pytest, pluggy, and iniconfig were retrieved through the existing connector,
isolated outside the repository, and verified against 91 upstream blob hashes
and byte counts. No alternative test implementation was substituted.

Workspace evidence is under `/workspace/audit-artifacts/`: `BASELINE_TESTS.md`,
`baseline-pytest-polling.txt`, genuine JUnit results in
`baseline-pytest-polling.xml`, `baseline-pytest-polling-run.json`,
`baseline-pytest-collection.txt`, `baseline-installed-versions.json`,
`pytest-source-provenance.json`, `run_pytest_with_polling.py`, and the initial
timeout result. These are local verification artifacts, not product dependencies.
The inventory preserves their digests and the exact command for traceability.
The [baseline pytest log](audit/2026-10-12-baseline-pytest.txt) and
[JUnit results](audit/2026-10-12-baseline-pytest.xml) are also retained in the
repository, together with the [diagnostic scheduling entry point](audit/run_pytest_with_polling.py.txt)
as text. It is an environment-specific test harness, not an application runner
or dependency. GitHub's baseline `main` checks succeeded at the audited revision:
[run 38187309244](https://github.com/jmann358/Orbit-core/actions/runs/38187309244).
That is separate CI evidence, not proof of this host's runtime or devices.

## Architecture and verified foundations

| Area | Existing implementation and evidence | Practical limit |
| --- | --- | --- |
| Interface and chat | FastAPI serves an embedded responsive dashboard, session selection, paginated history, and `/chat`. SQLite persistence and pagination tests pass. | Browser conversation flows and startup lifecycle are not covered by the existing suite. |
| Model connection | Environment-configured localhost/OpenAI-compatible adapters and native Gemini requests. Mocked payload/history/usage tests pass. | No live provider was contacted; provider selection is configuration, not a model-independent adapter interface or routing engine. |
| Memory and continuity | Persisted candidates and project notes; approval required before prompt inclusion; opt-in heuristic extraction, provenance, lexical recall, and separate cloud-history consent. Tests pass. | No semantic retrieval, comprehensive sensitive-data detection, retention/conflict management, or automatic learning. |
| Goals and workers | Persisted allowlisted tasks, bounded retries, event logs, owner-approved sequential goals, fixed recipes, specialist capabilities, pause/cancel/recovery, and dispatch budgets. Tests include concurrency and tampered authorization. | One in-process worker is expected; specialist names route trusted functions rather than independent model agents. |
| Development workflow | Read-only inspections, revision-locked proposal previews, manifests, fingerprints, text screening, technical decisions, and user-mediated bridge records. Safety tests pass. | No autonomous commits, PR creation, patch application, semantic correctness guarantee, or deployment. |
| Candidate runner | Manual Linux/bubblewrap runner fails closed when prerequisites or approval are missing. Mocked command/timeout tests pass. | Actual namespace isolation was not exercised; no Mac runner exists. Temporary baseline-test copies are not security sandboxes. |
| Reliability foundations | SQLite backup utility verifies consistency/integrity, rejects overwrite, and restricts destination permissions. Backup tests pass. | No restore rehearsal, uptime supervision, host monitoring, or tested Mac migration. |
| Ecosystem | Local presentation settings, static integration catalog, on-demand suggestions, and device/evidence readiness reports. Tests pass. | Voice, connected apps, paid routing, authenticated phone access, and remote deployment are absent. |

The application and database operations share a large `app.py` and `luna/core.py`.
Smaller modules already provide useful boundaries; retain them and separate
responsibilities incrementally. Identity and stored state are provider-independent,
while provider request/response logic is currently embedded in `core.respond()`.

## Prioritized defects and gaps

| Priority | Finding at audited revision | Required outcome |
| --- | --- | --- |
| P0 | An OpenAI-compatible `content: null` is returned as an answer and reaches SQLite's NOT NULL constraint; `/chat` fails with HTTP 500. Empty, whitespace, or non-string content is not rejected. | Validate response text before persistence; return a truthful bounded failure, preserve the user turn, and prove recovery with a subsequent valid reply. |
| P0 | URL parsing and cloud port validation occur outside the model failure handler. Malformed IPv6 raises there; invalid local ports can raise HTTPX `InvalidURL`, which the handler does not catch. | Validate configuration before requests and persist a readable reply without leaking endpoint details or relaxing the host allowlist. |
| P1 | Chat submission has no pending-send guard or captured response-session check. Switching sessions while awaiting a reply can display that reply in the wrong conversation; repeated submissions can overlap. | Bind each request/result to its source session and verify delayed-response and duplicate-submit behavior. |
| P1 | Draft/plan endpoints infer model failures from string prefixes. Some configuration/setup responses can be saved as successful proposals. | Introduce explicit response outcomes and test every model-backed drafting caller. |
| P1 | `with sqlite3.Connection` commits/rolls back but does not close the connection; helpers rely on later object cleanup. | Bound database handle lifetime without changing transaction semantics; verify locks and concurrent access on disposable databases. |
| P1 | Backlog dispatch uses separate transactions for reservation, job creation, and linking; unlike goal dispatch it is not atomic. | Test competing ticks and interruption points; avoid duplicate/orphan jobs and enforce limits transactionally. |
| P1 | Launcher copies only the default database with `cp`, after pulling source; custom `LUNA_DB_PATH` and SQLite-consistent verification are absent. | Coordinate with existing PR #12 and reuse the verified backup utility with explicit recovery evidence. |
| P1 | `README.md` and `readme.md` coexist, creating a checkout collision on typical case-insensitive Mac filesystems. | Retain one canonical README and verify a case-safe source tree before Mac installation. |
| P1 | Documented quickstart runs pytest, but runtime requirements omit it; Python minimum and tested platforms are inconsistent. | Provide a separate test setup and one supported Python policy, then verify clean setup when available. |
| P2 | No authentication or device pairing; permission policy is not an identity mechanism. | Design and obtain approval for authentication, pairing, encrypted transport, revocation, and retention before network access. |
| P2 | Provider telemetry and unattended-budget counters are separate; no hard spend enforcement exists. | Separate response adapters, model configuration/status, usage accounting, and approved resource limits; treat unknown usage/prices as unknown. |

The initial P0 provider-response validation/configuration slice is implemented
and has automated regression evidence: 37 new cases, 219 total passing tests.
This also rejects invalid UTF-8 text before persistence. A separate test
dependency manifest and startup documentation corrections are included.
Post-change results belong in [PROGRESS.md](PROGRESS.md); this table records the
baseline defects, not a claim that every listed issue remains unfixed.

## Documentation, dependencies, and integration status

- Runtime requirements declare FastAPI, Uvicorn, and HTTPX with broad ranges.
  The standard library supplies SQLite and most tooling. Pytest is a separate
  test dependency; optional Node checks skip if Node is missing. Bubblewrap is
  Linux-only and optional for normal chat startup.
- CI runs syntax and pytest checks on Linux/Python 3.13. The README says 3.11+;
  `docs/RUN.md` says 3.10+. No Mac M4 or iPhone QA has been recorded.
- `docs/RUN.md` says cloud calls send 20 recent messages; current chat context
  uses 30 plus approved memories/project notes and opted-in recall excerpts.
- Older workbench and manifest docs contain stale scheduler/API milestones.
  `orbit_tasks.json` retains planning tasks for already-built foundations.
  `PRIORITY5_COMPLETION.md` contains literal `\n` text that breaks rendering.
- Provider token metadata is recorded for successful responses, but the
  overnight token-budget hook is not wired to those events. Neither mechanism
  proves monetary limits. Static catalog entries are not connected accounts.
- Existing open PRs [#12](https://github.com/jmann358/Orbit-core/pull/12)
  (launcher), [#3](https://github.com/jmann358/Orbit-core/pull/3) (diagnostics),
  [#2](https://github.com/jmann358/Orbit-core/pull/2) (syntax screening), and
  [#1](https://github.com/jmann358/Orbit-core/pull/1) (sprint work) need
  coordination before overlapping implementations. They are not merged or
  treated as verified local functionality by this audit.

## What was not established

No live model response, paid-provider use, interactive browser chat, app lifespan
or real listening server, Mac installation, iPhone connection, restore rehearsal,
external integration, or public deployment was verified. Most model tests use
mocks; TestClient tests do not enter its lifespan context. Optional JavaScript
syntax and HTML-contract checks do not prove user interaction. Keep these
limits visible when reporting product readiness.
