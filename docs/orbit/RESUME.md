# ORBIT/Luna — permanent resume point (public-project metadata only)

**Start here every session, including fresh ChatGPT/Codex/Gemini or a replacement AI.**
This is a durable source record, not a chat memory service. Access to this repository is required. The keyword `POJO RESUME` helps locate it, but cannot automatically grant access or supply hidden conversation history.

## Minimum read, not another full audit

1. Read **`docs/orbit/STATE.json`**, then execute `python scripts/orbit_resume.py --json` and **`python scripts/orbit_resume.py --audit`** in a checkout. The audit checks reference hashes and the acceptance ledger without running Luna; fail closed on invalid metadata.
2. Check current GitHub `main`, the candidate and its stacked PRs in `STATE.json`, and newer comments in [issue #52](https://github.com/jmann358/Orbit-core/issues/52). Live THRONE status requires a host check. Treat conflicting reports as **unknown** until reconciled; don't downgrade new evidence because an old document disagrees.
3. State in two sentences: **current priority** and **first executable next step / precise blocker**. Don't replan completed source-review and design work.
4. Before editing, check the changed-file set, target SHA and any active owner or agent workstream. Never overwrite unmerged work. Check `DEVELOPMENT_POLICY.md` for sensitive permission gates.
5. Work on only the next unblocked task in `STATE.json`, with tests, evidence and explicit stop conditions. Prefer the 333-case ledger and specs in `docs/orbit/reference/` over requesting that the owner upload old ZIPs.
6. After real change: add a guarded checkpoint (`scripts/orbit_resume.py --checkpoint ...`), commit it on a dedicated branch, cite immutable evidence, and record **implemented vs verified vs released** distinctly. Git/GitHub review must catch concurrent changes. Do not update a status from an untrusted model assertion alone.
7. If the owner has a new idea, put a *sanitized project idea* into `IDEAS.jsonl` or propose the text. Show how it relates to current focus; it is **parked, not promoted** without owner decision. Do not nag or override an explicit change of priority.

## Right now (2026-10-13 checkpoint, not live host telemetry)

- **Current source focus P1-3 (source preparation only):** pinned Linux ARM64 dependency recipe, 22 wheel hashes and tested package versions verified without installation; image unbuilt. Apple container 1.5.0 source exposes host-side missing-image pull fallback despite guest network none. Next: establish approved runtime/application/init/kernel identities and candidate-time offline enforcement, then approved build/guest baseline/hostile isolation. No Mac execution or installed autonomy is established.
- **Live-update gate P0-0:** read-only Git inspection verified installed `560419d` with 12 tracked edits. Preserve those edits. The owner confirms independent encrypted backup/recovery is still pending and explicitly requests continued source work. No private database, installation or service change is authorized by this checkpoint.
- Privacy gate and the 40-attempt ceiling are in inspected `main`; health verification is stacked drafts #66/#67. Credit-aware routing remains its own queued work item (`P1-CREDIT`).
- Source-reviewed and design-ready: eight contracts and 333 proposed scenarios. `NOT_RUN` means exactly that; past 502-pass CI applies only to PR #58's existing suite, not these new requirements.
- Inspected `main`: `b707f80`; release label remains `pojo.2`. Candidate base: draft #72 at `5cb5b44`, stacked on #71/#70/#69/#68/#67/#66. Source continuation: `codex/luna-pinned-test-environment`. This stack is unmerged and distinct from the installed checkout. Re-fetch before acting.
- No new spending, new provider accounts, public exposure, generated-code application, or private-data upload is authorized by project documents.

## Drift control — the respectful checkpoint

If the owner proposes work outside the currently active priority, say: 
> "I can capture that. Our current priority is **[work ID/goal]** because **[blocker/dependency]**. I recommend **[next bounded action]**. Should I park this idea or explicitly change the priority?"

For a short creative diversion, do not require a formal decision. No idea should silently disappear; never imply an idea was saved to GitHub unless a commit actually occurred.

## Keep records distinct

- `STATE.json`: current machine-readable priority and lifecycle, guarded revision and chain of checkpoint events. This is mutable by *reviewed Git commit*, not a truth oracle.
- `IDEAS.jsonl`: append-only idea inbox, no implied priority or permission.
- `reference/`: versioned design contracts, test plans, archival prior handoff documents. These are **not tested product features**.
- Issue #52: dated operational evidence and pointers, not live installed-state telemetry.
- Protected private SQLite on THRONE: Luna's actual personal memory, never replicated into GitHub for continuity.

**No guarantee of remembering across arbitrary providers:** the practical guarantee is persistence **of the files and Git history**, not automatic access, perfect state accuracy, or an unexpired API connection. A new agent must read these files (or be given their contents) to resume.

## Continuity maintenance rule

The state pointer can change after new evidence, but never erase an old event. Run `--audit` on the reference package after intentional changes; update its SHA-256 manifest in the same reviewed commit. Any completed acceptance case must have actual tested-revision and proof. The hash chain is tamper-evident *within a given file*; Git commit history and reviewer oversight, not the hash chain alone, provide independent auditability.
