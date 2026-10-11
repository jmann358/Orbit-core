# ORBIT · Luna

ORBIT is a provider-independent AI agent ecosystem. **Luna** is its central assistant.

## Status
**Phase A — repository foundation only.** No assistant is deployed, no model API keys are configured, and no background processes are running.

## Principles
- Identity, memory, permissions, and goals are independent of model providers.
- Start with free/local resources; escalate to paid models only when justified and authorized.
- Preserve conversations and extract useful memories with reviewable provenance.
- Record improvement opportunities without spending tokens on constant self-reflection.
- Test upgrades in isolation; require human approval before deploying core changes.
- Never bypass quotas, register accounts, or spend money without authorization.
- Mac M4 mini is the planned local host; iPhone/iPad access comes later.

## Next steps
1. Implement a local-first Python core with SQLite memory and append-only improvement journal.
2. Add a resource router with a strict zero-spend default.
3. Add tests and a simple private chat interface.
4. Review security before exposing anything to the internet.

See [architecture](docs/ARCHITECTURE.md) and [decisions](docs/DECISIONS.md).
