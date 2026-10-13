# POJO.3.1.0 — Three-Station Flight Operations

**Status:** Coordination protocol and proposed work allocation, not an installed feature or a grant of runtime permissions.

**Purpose:** Three devices can contribute safely without conflicting Git branches, duplicating local databases, exhausting a computer's CPU, or fragmenting project context.

## The three codewords

| Codeword (say at the start of a new chat) | Device | Role | Work owned |
|---|---|---|---|
| **POJO HELM** | iPhone | Mission control / integrator | Priorities, GitHub PR reviews and integration sequencing, owner permissions, current ship status, implementation decisions, safe remote source changes |
| **POJO ATLAS** | iPad | Architecture, QA and independent second review | Review audits, complete launch acceptance matrix, check security boundaries, simplify UX / approvals, write specifications or non-overlapping tests/docs on a separate branch |
| **POJO ENGINE** | Currently loaded computer (Chromebook/Linux until Mac is ready) | Local evidence / real-world systems | Short read-only CPU/RAM/load checks, safe local startup and provider diagnosis, actual host smoke results, backups and migrations only after explicitly authorized staged steps |

**Handoff/recall is not authentication.** These phrases only identify the requested workstream and do not grant tool, repository, account, device, spending, or release rights. The existing `SASHIMI POJO` phrase can continue to mean general context recovery, not a fourth independent development authority.

## One project, not three independent projects

- **Single current program:** Pojo.3.1.0, repo `jmann358/Orbit-core`.
- **Stable published baseline:** pojo.2 / main, SHA `baf96abff8105b89e7b4c924ff03921f084923b5` (verify fresh GitHub on each session).
- **Current single integration candidate:** draft PR **#38**, `release-candidate/pojo-3-1-0-mac-flight`. The branch must not be treated as installed or merged. Re-fetch exact PR head before changes.
- HELM decides which scoped branches are being integrated. ATLAS must write separate files/branches and must not modify HELM's branch in parallel. ENGINE must never change live DB, force-pull, kill services, or install software to resolve branch conflicts.
- The three workstreams each report the same short status fields: **baseline SHA, changed files or evidence, test results, blockers, next action, owner approval required**. The project docs/PR descriptions are the durable handoff across chats. Never assume a codeword synchronizes entire invisible chat histories automatically.
- Do not run simultaneously writable copies of Luna against the same SQLite memory. The authoritative existing Chromebook data stays authoritative until a consistent backup, integrity-checked Mac transfer and single-writer cutover are separately approved and verified.
- No deployment/merge/release, paid API, sensitive credential/device access, unsafe generated-code execution, mobile network exposure or destructive data change without separate explicit owner approval.

## Work sequence and load budgeting

### Wave 1 — now, without the Mac

**HELM:** Validate final PR #38 head and CI; review audit findings and unblockable bugs, create scoped review PRs rather than merge old PR #1; retain one combined launch candidate; maintain the release-blocker board.

**ATLAS:** Independently evaluate the Flight Plan acceptance tests versus actual GitHub modules and code, flag hidden assumptions and missing checks, improve sequential inline approval and result UX contracts, create review-only docs/tests without crossing HELM's files.

**ENGINE:** Only brief local diagnostics on the already-overloaded Chromebook. If load is high, let GitHub Actions handle `compileall` and the full Python test matrix; use the computer for targeted live-host evidence and small local checks. Do not start extra local AI models, full test suites, or duplicate service instances merely to keep it busy.

Linux read-only workload probe, if explicitly run on the Chromebook:

```bash
uptime
free -h
ps -eo pid,pcpu,pmem,comm --sort=-pcpu | head -n 12
```

Interpret output before proposing any stop, uninstall or configuration change. Do not share sensitive environment variables or application database contents.

### Wave 2 — one usable supervised Luna

Review and owner-approve an integration path. Verify a configured local model answers genuinely, chat and memory persist, two-step approved mission produces linked worker receipts after a restart, backups are recoverable, and the UI accurately describes real status. Verify on the actual target host, not only in cloud CI.

### Wave 3 — self-sufficient Luna

Build and verify safe generated-code isolation + bounded test/repair/revert, general permission-aware goal planner, resilient ongoing worker orchestration, owner-sensitive contextual approvals that resume without needless interruptions, trustworthy result verification, secure single-home mobile authentication and revocation, and reliable Mac power/recovery behavior.

## Definition of done: no percent-complete theater

The prior 43-finding audit is a *finding count*, not a percentage of the product left. Passing 418 automated tests on the CI runner at one specific candidate revision only verifies those enumerated scenarios. It does not establish a live Mac inference provider, real restored memory, secure code sandbox, voice, iPhone pairing or general autonomy.

**Near-term exit:** reliable, owner-approved work on one actual host, consistent state and one restart/restore pass.

**Full autonomy exit:** owner can specify a bounded goal, Luna makes an authorized plan, performs it or requests *contextual* permission, resumes after approval, verifies outputs, recovers interruptions, and returns a durable directly accessible result without source/data loss or unauthorized spending.

## Response protocol

- `POJO HELM — status`: Re-fetch GitHub main, PR #38 and latest CI; provide the next safe integration action and owner decisions, avoid redundant questions.
- `POJO ATLAS — audit`: Read the Flight Plan and current PR changes; review acceptance gaps independently and post an evidence-based discrepancy report.
- `POJO ENGINE — diagnose`: Give one read-only command at a time on the currently available computer and interpret the pasted results; avoid CPU-intensive local actions.
- End each session with a 5-line GitHub-grounded handoff: **revision / verified work / blockers / handoff target / pending authority**.

**Source of truth is GitHub and the owner's verified host state, not codeword lore.**