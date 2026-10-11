# Priority 5, phase two: bounded specialist directory

The system now declares three *static* specialist identities:

| Specialist | Allowed job kind |
| --- | --- |
| Project Inspector | `project_health` |
| Repository Researcher | `github_status` |
| Development Planner | `development_plan` |

`GET /agent/specialists` exposes the read-only capability directory.
`GET /agent/goals/{id}/report` labels each planned step with its specialist.
Goal proposals fail closed if any step lacks an explicitly declared specialist.

These are **routing labels for the existing trusted task handlers**, not
independent AI model sessions, new credentials, subprocesses or plugins.
The registry is immutable at runtime; API responses are copies. No agent
can change its own capability list, execute arbitrary code, spend money,
or grant new permissions.

The approval and audit boundaries from phase one still apply. No
additional dependencies, cloud requests, credential scopes, device access,
model calls or deployments are introduced. Do not expose the existing
unauthenticated localhost dashboard to any network.

Before real multi-agent execution, implement authenticated access,
per-agent runtime enforcement, explicit approval for each new capability,
backups, actual usage metering and end-to-end local QA.
