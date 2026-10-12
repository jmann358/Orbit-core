# Luna: zero-cost cloud readiness and self-hosting boundary

This is a **dry-run plan**, not a deployment. It requires no cloud account, payment method, AI provider key, public URL, or transfer of personal memory.

## What Luna can do herself today

Luna's worker can queue bounded source improvements and prepare reviewable, revision-locked proposals. It cannot create cloud accounts, configure GitHub credentials, buy hosting, deploy code, or grant itself permissions. These restrictions are intentional. A worker that could expand its own privileges would defeat the owner's approval policy.

## Zero-cost cloud experiment

1. Run all checks in GitHub Actions using the existing repository workflow. This validates deployable code without hosting Luna or exposing personal data. CI minutes and quotas depend on GitHub account and repository settings; confirm availability before relying on them.
2. Build a **disposable, stateless** test instance from source only. Do not mount or copy the owner's existing SQLite database, conversation history, private keys, secrets, or backups.
3. Use a dedicated temporary database created at startup. Seed it with synthetic conversation and development-mission data only. Never point any test service at the production/local database.
4. Keep the service **private** until authenticated mobile access and CSRF protections have been verified. A bearer token in environment variables is not a secure browser sign-in.
5. No outbound paid model requests. Model-backed tests should use a fake local HTTP model; any real provider requires a separate explicit opt-in.
6. Require a verified backup-and-restore procedure before a real cloud instance becomes the primary home for persistent Luna memory.
7. Destroy the disposable instance and test database when the test finishes. A free service that sleeps, resets storage, or expires must never be the authoritative memory store.

## Self-deployment agent: proposed safe capabilities

An eventual deployment controller may:
- Read repository and CI status.
- Generate deployment manifests, Dockerfile, infrastructure configuration and test plans on a feature branch.
- Validate configuration locally and in CI without credentials.
- Report predicted resource use and costs.
- Open a pull request for owner review.
- Observe health checks and logs with read-only, narrowly scoped credentials.

It must **not**:
- Create an account, add a payment method, authorize costs, or elevate its own access.
- Publish the service, enable public networking, upload memories, or install unreviewed generated code.
- Merge its own pull requests or change branch protection, security rules, or approval gates.
- Copy credentials into prompts, logs, source control, or development missions.

## Preconditions for a real deployment

- Owner selects and connects a hosting account with narrowly scoped permissions.
- Owner approves the first network exposure and a verified mobile authentication flow.
- A persistent encrypted store and tested restore process exist for real memories.
- Spending ceiling, model request limits, and usage alerts are configured. Call limits alone are **not** a dollar limit.
- An approved deployment identity is separate from Luna's source-editing identity.

## Current status

**No cloud service created. No paid service created. No personal memory migrated.**

The only automatic action authorized here is preparation of reviewable code and checks in GitHub. A live, independent cloud Luna is not yet available.
