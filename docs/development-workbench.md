# ORBIT development workbench — v0.6.0

## What's implemented

- Public GitHub Actions regression checks on pushes and pull requests.
- Read-only GitHub test status and shared task queue in the local dashboard.
- Explicit local allowlist for shared task execution (DEV-001, DEV-002, DEV-003).
- DEV-001 checks project syntax/structure and the latest GitHub workflow result.
- DEV-002 and DEV-003 generate fixed, local engineering checklists. They do **not** autonomously write code or call a model.
- Shared task outcomes persist in SQLite and can be reviewed in the dashboard.
- Static draft syntax screening parses fenced Python blocks using ast.parse without executing or applying the code.
- Opt-in in-process maintenance timer for read-only health and GitHub checks.

## What is NOT implemented

- ChatGPT and Luna cannot talk directly in real time. GitHub is the exchange medium.
- Luna cannot independently submit GitHub changes, create PRs, or deploy patches.
- A green CI check does not establish safety or authorize installation.
- Static syntax checks do not establish patch applicability, correctness, or security.
- Temporary test directories are not an OS security sandbox. Never run untrusted model-generated tests or code there.
- The scheduler is in-memory, starts disabled, and does not survive process restart.

## Trust boundaries

1. GitHub task descriptions are untrusted display data; IDs and execution capabilities must match the local allowlist.
2. No remote task body is interpreted as Python, a shell command, or a URL to fetch and execute.
3. Local execution remains confined to fixed operations.
4. Spending, secrets, permissions, external services, publishing, deletion, and deployment require owner approval.
5. Keep the server bound to 127.0.0.1 until authentication and network threat controls exist.

## Next development milestones

1. Machine-readable draft format with file allowlists and exact base revisions.
2. Static patch applicability check, diff preview, and provenance records.
3. Secure external sandbox for untrusted code execution; never assume a temporary directory is enough.
4. Signed or authenticated bidirectional task status exchange, with narrowly scoped credentials.
5. Durable scheduler with persisted enable state, task leases, and a kill switch.
