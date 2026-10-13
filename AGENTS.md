# ORBIT/Luna durable project resume — first step for every AI session

Before proposing work, read [docs/orbit/RESUME.md](docs/orbit/RESUME.md) and `docs/orbit/STATE.json`. In a checkout run `python scripts/orbit_resume.py --json` and `python scripts/orbit_resume.py --audit`. Verify current GitHub heads, issues and actual host state, then do only the next authorized unblocked work. Do **not** repeat the completed eight-section design review; record new ideas in `docs/orbit/IDEAS.jsonl` instead of silently changing priority. This is a public-code metadata handoff, not permission to merge, deploy, access private data, or spend money. See [issue #52](https://github.com/jmann358/Orbit-core/issues/52) for later checkpoints.

# ORBIT/Luna development instructions

ORBIT is the control room. Luna is the central assistant. Her identity,
personality, conversations, approved memories, goals, and permissions belong
to ORBIT and must remain independent of the inference provider. The intended
primary home is a Mac M4 mini; authenticated iPhone and other device access
is future work.

## Delivery priorities

1. Deliver reliable conversations and persistent, owner-reviewed memory.
2. Fix failures that prevent local startup or lose or misrepresent user data.
3. Preserve working code and existing architecture wherever practical.
4. Build on verified behavior; do not rebuild the project from scratch.

## Before changing code

- Read these instructions, `DEVELOPMENT_POLICY.md`, `docs/AUDIT.md`,
  `docs/ROADMAP.md`, `docs/PROGRESS.md`, and relevant decision entries.
- Establish the exact source revision, inspect the affected code and callers,
  and run existing relevant tests before implementation. The initial complete
  repository audit is recorded in `docs/AUDIT.md`; update it when evidence
  changes rather than treating old findings as current verification.
- Inspect open branches and pull requests before duplicating work. Record
  baseline commands, results, environment limitations, and reproducible defects.
- Keep conversation databases, backups, credentials, and private transcripts
  out of Git, pull requests, logs, and test artifacts. Use disposable SQLite
  databases and fake credentials in tests.

## Safe autonomy and review

- Carry out authorized safe, reversible source, documentation, and testing
  work without stopping for routine implementation choices.
- Use focused branches and reviewable pull requests. Never merge to `main`
  without owner approval. Do not deploy or expose the service publicly without
  explicit approval.
- Preserve model endpoint restrictions, memory review, continuity/cloud
  consent, worker allowlists, goal approvals, and permission boundaries.
  Never bypass a control to make a test pass.
- Follow `DEVELOPMENT_POLICY.md` for sensitive actions, dependencies, paid
  provider calls, external services, and access expansion. Current explicit
  user instructions and existing session authorization take precedence.
- The unauthenticated app must remain bound to `127.0.0.1`. Remote access
  requires an approved authentication, pairing, transport, and revocation
  design before implementation or exposure.
- Generated proposals, fingerprints, passing tests, and green CI do not
  authorize code application, deployment, permission expansion, or spending.

## Verification and maintenance

- Prefer existing dependencies and interfaces. Add regression tests that
  exercise a reproduced failure and observable behavior, not implementation
  details. Verify changes with appropriate tests and the full trusted suite.
- Normal verification: `python -m compileall -q app.py luna tests` and
  `python -m pytest -q -p no:cacheprovider tests`, using the documented test
  dependencies. Never silently skip a failure or replace an unavailable
  test runner with a fabricated result.
- Document mocks, skipped checks, test-only workarounds, and unavailable
  hardware/providers. Mocked responses do not establish live model access;
  HTML or JavaScript syntax checks do not establish an interactive UI.
- Update `docs/ROADMAP.md`, `docs/PROGRESS.md`, and `docs/DECISIONS.md` as work
  advances. Report exact test counts and outcomes, never completion percentages.
- A change report or PR must state the problem, resulting behavior, evidence,
  material limitations, and remaining work. Never claim something works unless
  it was verified at the reported revision.

## Code review guidelines for Codex

Review source behavior rather than green CI alone. Flag as P0/P1 when a
change could lose approved memories, send user data or credentials to a
provider/GitHub without consent, weaken authentication, expose the localhost
service publicly, execute generated code on the live host, grant itself
permissions, or authorize paid calls/merges/deployment without owner approval.
For startup/backup changes, test custom `LUNA_DB_PATH`, SQLite WAL and source
integrity, symlinks, permissions, incomplete snapshots and process cleanup.
For conversation changes, test invalid provider responses, delayed replies,
session switching, retry recovery and actual model readiness. Check failure
messages against observed state. Clearly identify mocked-provider tests versus
verified host/network/device behavior. Propose small reproducible fixes and
bounded regression tests; don't claim live deployment.
