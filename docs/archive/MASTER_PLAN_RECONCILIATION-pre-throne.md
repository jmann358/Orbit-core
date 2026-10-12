# Master-plan reconciliation — ORBIT/Luna

Review baseline: `docs/ARCHITECTURE.md` (initial architectural charter),
`docs/PRIORITIES6_14_DEVELOPMENT.md` (priorities 6–14),
`docs/ROADMAP.md` (acceptance criteria), `DEVELOPMENT_POLICY.md`
(owner authority), and `AGENTS.md` (Codex instructions).
This is a gap register, **not a declaration that all original goals are complete**.

## Original commitments and current evidence

| Master-plan promise | Present implementation | Remaining acceptance work |
| --- | --- | --- |
| ORBIT control room and Luna identity | FastAPI dashboard, Luna system charter, provider-independent SQLite state | Live UI acceptance and owner preference review |
| Persistent conversation and approved memory | Saved sessions, paginated history, memory candidates, approved context, local backups | Real browser reconnect, long-term conflict/retention policy, verified restore on target host |
| Model/provider independence | Local/OpenAI-compatible/Gemini adapters and separate developer model | Real local inference, provider failover and verified hard cost limits |
| Autonomy with owner approvals | Fixed job worker, scheduler, mission queue, draft GitHub PR publishing behind opt-in | Live self-build run, complete test-repair loop, reliable long-running supervision |
| Many specialized agents | Specialist handoff envelopes and bounded goal recipes | Separate isolated agent runtimes, scoped identities and real coordination |
| Mac M4 mini and iPhone | Loopback launcher, device readiness reporting, responsive UI | Mac installation, secure pairing/authentication, TLS, revocation, iPhone smoke test |
| Cloud portability | Cloud mode security gate and independent queue foundations | Owner-approved private deployment, durable cloud storage and disaster recovery |
| Voice and expressive avatar | CSS ghost companion, saved visual settings | Actual voice input/output, accessibility and richer animation |
| Skills and integrations | Catalog and permission proposals | Real connectors, scope lifecycle, integration tests |
| Proactive behavior and budget control | Local suggestion review, bounded scheduler, token metadata | Owner-approved notifications, meaningful resource allocation and enforced cost ceilings |
| Self-improvement and reliability | Source revision checks, draft PR path, tests, local snapshots | Live model evidence, automated safe testing/repair, rollback and host monitoring |

## Fixed in this focused pass

- Remove `readme.md`, which conflicts with `README.md` on the intended
  Mac's default case-insensitive filesystem.
- Enforce a tracked-file case-collision guard in CI.
- Add a disposable SQLite restore rehearsal that never overwrites the real
  conversation database. Unit tests prove existing data remains intact.

## Critical path before the owner hands work to Luna

1. **Live model-backed chat and self-build** on the intended always-on host.
   Existing CI only mocks provider interactions.
2. **Supervisor and restart test**: prove worker and chat recover from crashes
   and computer restarts without losing state. A terminal foreground process
   does not meet the 24/7 requirement.
3. **Real development acceptance**: generated patch -> isolated trusted tests ->
   feedback -> one bounded repair -> draft PR -> owner review. Never auto-merge
   generated changes or run them in the live memory-bearing process.
4. **Authenticated iPhone access** after owner approves a pairing and
   revocation design. Do not expose the unauthenticated loopback app.
5. **Recovery and privacy**: local restore rehearsal on the real host,
   encrypted backups, memory retention choices and proof no private data
   reaches GitHub PRs or model-development prompts.

## Codex review request

Have Codex independently review this PR **and the full repository**, starting
with `AGENTS.md`, `DEVELOPMENT_POLICY.md`, `docs/ARCHITECTURE.md`,
`docs/ROADMAP.md`, `docs/AUDIT.md`, and this reconciliation.

Prioritize security and user-visible defects over features:
- Check that GitHub draft PR publishing cannot disclose secrets, run
  untrusted generated code, merge or expand its own privileges.
- Check model discovery and local-only guarantees in
  `scripts/start_luna_agent.py`.
- Review SQLite backup and restore behavior with WAL mode, symlinks, custom
  database paths, concurrent writers, failure cleanup and permission bits.
- Reproduce pending-send/session-switch behavior in browser interactions.
- Check lifecycle and recovery under multiple workers and interrupted jobs.
- Identify stale documentation, duplicate implementations and missing tests.
- Produce a focused PR with fixes and real CI evidence. Do not deploy, connect
  accounts, spend money or edit personal memory.

**Codex has not been verified to run merely because this prompt exists.**
The owner or an authorized connected Codex workflow must launch that review.
