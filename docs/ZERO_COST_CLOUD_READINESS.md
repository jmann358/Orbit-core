# Luna: zero-cost cloud readiness and self-hosting boundary

This documents the **implemented, review-gated self-building handoff** and a proposed disposable cloud test. It is not a deployment. No cloud account, payment method, AI provider key, public URL, or personal-memory transfer was created.

## What Luna can do herself today

Luna's worker can queue bounded source improvements and prepare revision-locked proposals. The new self-build supervisor can start the next mission, reverify its source fingerprint, and publish it automatically as a **draft GitHub PR** *after* a separately approved repository-scoped token and opt-in are configured. These are code review requests, not deployments. She cannot create accounts, grant permissions, buy hosting, merge code, or deploy code.

Self-building APIs, available only after the owner starts the app:
- `GET /agent/self-build/status` — report verified blockers (without exposing credentials).
- `POST /agent/self-build/start` — choose and queue one bounded improvement.
- `GET /agent/self-build/publications/{mission_id}` — see whether a PR was published.
- `POST /agent/self-build/publish/{mission_id}` — publish one prepared, verified proposal as a draft PR if separately configured.
- `/agent/studio` — contains a **Start Luna's next improvement** button.

The independent worker can take this further with these explicit, host-level controls:

```text
LUNA_WORKER_ENABLED=1
LUNA_AGENT_AUTO_ENABLED=1
LUNA_AGENT_MODEL_ENABLED=1
LUNA_MODEL_URL=<owner-approved endpoint>
LUNA_MODEL_NAME=<owner-approved model>
LUNA_GITHUB_PR_ENABLED=1
LUNA_GITHUB_PR_AUTO_ENABLED=1
LUNA_GITHUB_TOKEN=<repository-scoped secret, never committed>
```

For cloud AI models, `LUNA_AGENT_ALLOW_CLOUD=1` and a provider's key are separately required. Keep all keys in a secret manager; **never paste them in a chat, issue, source file, or PR.** Use the smallest possible token scope for the GitHub repository, with **contents + pull-request** access but no administration. The token is needed only if owner authorizes the publishing capability. Once configured, the worker runs the limited mission and publishes a *draft* PR for review, without asking the owner for each file.

**This is code that has passed mock-provider tests, not a claimed live model/GitHub provider run.** GitHub account/service connection, live model test, and always-on runtime remain outstanding. The worker's 2-model-attempts/day limit is not a monetary cost cap.

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

The prepared self-building code can create **draft feature-branch PRs only after opt-in and credentials are provided**. It cannot merge, deploy, or spend. A live, independently hosted Luna still requires a model and persistent runtime.
