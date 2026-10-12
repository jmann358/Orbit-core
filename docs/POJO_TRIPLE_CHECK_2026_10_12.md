# POJO / Luna triple-check — pre-Mac source and handoff review

**Snapshot date:** 2026-10-12. **This report is a remote GitHub source review, NOT actual Mac/iPhone/Chromebook acceptance.** Source base: cumulative draft #51 `2568b7d5432b4f30de33402f075c5dae9510fafe` on unchanged published `main` `baf96abff8105b89e7b4c924ff03921f084923b5`, application `pojo.2`.

**Live long-term handoff:** [GitHub issue #52 — POJO RESUME](https://github.com/jmann358/Orbit-core/issues/52). This is the ONLY living context index. Read `AGENTS.md` and `DEVELOPMENT_POLICY.md`, then fetch fresh refs: the exact SHAs below are an immutable October evidence snapshot, **never** assume they remain current in a month.

## Pass 1 of 3 — branch, release, duplicate and historical reconciliation

| Audit item | Verified finding | Action |
| --- | --- | --- |
| Published software | `main` still `pojo.2`, not upgraded by draft PRs | Preserve baseline; do not claim `pojo.3` released |
| Cumulative flight draft | `#38` → `#45` → cumulative `#47` → ENGINE stage `#48` → developer-model & workflow stage `#51` | **One integrated review path**; do not merge the overlapping earlier PRs separately |
| Duplicate branch #46 | ENGINE fixes are already reconciled in #48 | Keep #46 only for provenance; skip duplicate application |
| Duplicate branches #49/#50 | Their two changed files + test file are already combined in #51 | Do not merge #49 or #50 on top of #51 |
| Small historical drafts #32–#37 / #40 / #42–#44 | Overlapping/stacked work already imported to #38/#45 and hence #51 | Retain as history; source-level verification, not independent release imports |
| Former "session-continuity" branch / PR #2 | `docs/session-continuity-playbook` actually modifies `docs/VALIDATOR_REVIEW.md`, `luna/development.py` and `tests/test_development.py`, **not** a live session recovery mechanism | Do not infer continuity from the branch name; use issue #52. This older diverged branch is not a source-of-truth |
| Old "loopback-csrf" branch | `cb13f7c...` is an ancestor of combined #51 (0 ahead, 47 behind), with no missing branch-only changes compared with #51 | No duplicate import; name does not establish authenticated mobile pairing |
| Historical PR #1 | Diverged by 240 commits ahead, 105 behind the candidate; 111 changed paths; known conflicts / unverified execution paths | **Not safe to mass-merge**; security-focused semantic review on isolated paths before any import |
| ATLAS PR #41 | Independent documentation-only initial audit of #38, predates later fixes | Require fresh review of #47/#48/#51, not a recycled signoff |
| Financial PR #28 | Diverged and intentionally separate | Explicit owner finance and consent gate, not part of Mac first flight |

**Duplicate proof:** GitHub compare and pull-request `base`/`head` data, not PR titles or test counts. The latest #51 head passed **458 tests on both Python 3.11 and 3.13 in two complete runs**, but that does not establish zero product defects.

## Pass 2 of 3 — source, security, startup and evidence checks

### P1: confirmed verified-update guard/workflow mismatch (RELEASE BLOCKER)

- File `scripts/verify_and_launch.sh` on #51 pins `TRUSTED_WORKFLOW_BLOB="3c13b96eb6a07782be68bf1e233eb6cdae7b048d"`.
- Updated `.github/workflows/orbit-checks.yml` on #51 is Git blob `90e8706d6d938d96fbb1968cb652f80f747c07bf`. The difference is **real**, not a guessed mismatch. It came from the CI-maintenance checkout@v5/setup-python@v6 update.
- The protected launcher calls `verify_trusted_workflow` on both current HEAD and the future `main` target. Thus if #51's workflow lands in published `main` without a separately reviewed trust-pin decision, the launcher **intentionally refuses the start/update**, even if the 458 tests are green.
- **Do not auto-change the pin** to make tests pass. Security-sensitive trust anchor changes require explicit owner review/approval. The separate read-only `scripts/check_release_guard.py` reports actual Git blob equality; synthetic tests verify match, edited workflow, missing and ambiguous pins and the known candidate mismatch.
- Release gate sequence: independent source review of the new workflow; owner explicitly authorizes a new pin and migration plan; focused patch to the trusted launcher; rerun exact-head CI; simulate new and old workflow conditions; verify last-good rollback, including the *old on-disk launcher* trust behavior. Do not silently replace the source trust anchor.

### P1: Mac model, actual data, auth and sandbox proofs still absent

- The Mac one-time setup script may install Python packages, Ollama, pull a coding model, create/login-register a LaunchAgent. Its non-`--check` path is **not** a read-only readiness command and requires owner authorization. The default LaunchAgent self-builds using an installed local coding model; this is local draft generation, not a general secure self-modifier.
- `scripts/luna_one_time_setup.py --check` is an inspection only. A discovered model tag or configured endpoint is **not a completed model inference**; the setup script's full inference probe remains host-unverified.
- Chromebook SQLite is still the owner's canonical real history. No verified encrypted owner-controlled transfer, WAL-consistent snapshot/restore with schema/content counts, one-writer cutover or rollback rehearsal on the Mac is recorded. GitHub tests use disposable data. **Do not copy actual SQLite/WAL/SHM to GitHub.**
- The HTTP dashboard is unauthenticated loopback. **Do not expose to Wi-Fi, tunnels, proxies or the Internet.** Mobile pairing, revocation, cross-device CSRF/authentication and actual iPhone testing remain separate later permissions.
- Current sandbox tests are trusted subprocess tests. They do **not** establish safe isolation of arbitrary AI-generated code on macOS, automated code application, merge permission or rollback.
- ATLAS's later review, real browser/touch controls, model error/recovery, process restart, power/sleep and contextual plan-edit/reauthorization are still missing end-to-end host evidence.
- `luna/developer_model.py` #51 now fails closed on malformed candidate text, with 24 synthetic cases; this is a bounded improvement rather than a verified functioning real model.

### P2: ordinary preflight oversights to check at physical host

- Existing project checkout may not be present on Mac. First read-only session must report absence rather than invent a source installation.
- A Python 3.10 or broken old `.venv` is not automatically suitable; use supported Python 3.11+ and verified reviewed dependencies.
- A registered LaunchAgent is not proof of healthy running worker; ENGINE #46/#48 correct this description. A listener at port 8000 is not necessarily Luna; a pre-bind probe does not eliminate races.
- First-run recovery must preserve the previous known-good code and data. Do not automatically update to the draft checkout because CI passed.
- GitHub CI previously emitted Node 20 deprecation; #50/#51 updated the workflow and eliminated the warning, but consequently exposed the trusted-pin incompatibility above.

## Pass 3 of 3 — recoverable continuity without relying on ChatGPT memory

1. **Canonical stable record created:** [issue #52](https://github.com/jmann358/Orbit-core/issues/52) is immediately accessible in GitHub, independent of merging this audit PR, and contains the codeword, source map, safety gates and fresh-check instructions.
2. **Discoverability when branch is approved:** this audit adds short links near the top of `README.md` and `AGENTS.md` to the living issue, **without copying dated state into two competing handoffs**. Until approved and merged, `main` does NOT contain these pointers. The GitHub issue remains accessible regardless.
3. **Codewords:** `POJO RESUME` is the general lookup phrase; `POJO HELM WAVE 2`, `POJO ATLAS WAVE 2`, `POJO ENGINE WAVE 2`, and `POJO HELM — MAC READY` have separately documented device workstreams. They are neither credentials nor a way to grant runtime permission.
4. **New session steps:** access GitHub issue #52 using the connected GitHub app, retrieve live `main`/PR/CI/reviews and policy, reconcile overlapping changes, then give the five-line evidence handoff. If GitHub connection is unavailable, request app connection or source documents and **state what could not be verified**. Do not pretend past chats magically auto-synchronize.
5. **Monthly stale-state robustness:** fixed historical SHAs remain dated snapshots; next session must re-query live GitHub; update issue body after material milestones and append evidence comments with exact SHA, owner permissions and operating-system proof.
6. **Revisit and test** the living handoff after the approved version merge, a model/provider change, hardware cutover, or a security policy change. A successful retrieval of public GitHub docs **does not** retrieve the owner's private local memory.

## Accurate GO / NO-GO conclusion (2026-10-12)

- **Remote synthetic code quality:** PASS for enumerated tests at candidate #51, subject to independent review.
- **Release/verified-update path:** **NO-GO** until trusted workflow mismatch is separately approved and resolved with rollback evidence.
- **Actual Mac startup, AI replies, live SQLite restore, authenticated phone, secure AI-written code runner:** **UNVERIFIED/NOT BUILT** where indicated above.
- **Fully autonomous Luna:** **NO-GO**, pending missing owner approval/OS isolation/general planner and honest recovery.
- **Private data safety:** No actual private data accessed or moved during this remote audit.

**No mathematically defensible guarantee of "100%" exists from CI and remote review alone.** Entry to Mac must start with read-only diagnostics and explicit owner decisions before installs, data transfer or deployment.

## Five-line checkpoint fields (required each future session)

1. Published version and exact fresh `main` SHA.
2. Most recent *combined* draft SHA, exact test count/CI identity, independent review.
3. Real host/device/model/database proofs vs only mock/CI tests.
4. Highest-risk missing gate and duplicates to avoid.
5. Next non-overlapping safe task and every owner-only authorization still pending.
