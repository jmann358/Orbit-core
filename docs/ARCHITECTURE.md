> **Deployment decision:** THRONE is the sole Luna host and authoritative writer. iPhone/iPad are future authenticated clients. Optional external model/tool services are separate approved integrations, not a fallback host. See [FLIGHT_PLAN.md](FLIGHT_PLAN.md).

# ORBIT architecture — draft v0.1

## Boundaries
- **Luna Core:** assistant identity, personality configuration, goals, conversation state.
- **Memory:** local SQLite conversations, structured memory candidates, provenance, export.
- **Model adapters:** replaceable interfaces for local and cloud inference.
- **Resource manager:** task classification, provider selection, estimated costs, quotas, hard budgets.
- **Improvement journal:** errors, proposals, tests, measured outcomes; no automatic production deployment.
- **Governance:** permissions and explicit approval gates for sensitive operations.
- **Interface:** private responsive web chat; no public exposure by default.

## Safe initial execution
The first version will not automatically edit its own deployed code, create provider accounts, purchase tokens, or run arbitrary commands. Experiments occur in isolated branches or test environments with human review.

## Resource strategy
1. Reuse cached knowledge or deterministic tools when sufficient.
2. Prefer suitable local/free models.
3. Use approved cloud resources within a defined budget.
4. Request permission before any new charge or elevated access.

A free model that repeatedly fails may be less efficient than a low-cost paid model; routing should measure success, not only price.
