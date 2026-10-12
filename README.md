# ORBIT · Luna

ORBIT is a local-first, provider-independent assistant ecosystem. Luna is its conversational coordinator.

## Priorities 6–14: local-first foundations (under development)

The next milestone adds review-only chat memory extraction, traceable
specialist handoffs, device-security readiness, real provider-reported token
usage accounting (prices unknown), persisted avatar presentation choices,
a static integration catalog, on-demand proactive suggestions, improvement
evidence gates, and verified offline SQLite backups.

These foundations are **not** nine completed priorities. In particular,
authenticated iPhone access, independent model agents, paid provider routing,
microphone/voice, connected apps and remote deployment still need explicit
owner decisions and additional work. No new subscriptions, external access,
provider calls or automatic code application are enabled.

See [Priorities 6–14 development and safety](docs/PRIORITIES6_14_DEVELOPMENT.md).

## Luna 1.0 release candidate — agent core

The **Goals** tab supports persisted objectives, owner-reviewed action plans, sequential execution of three allowlisted low-risk tools (local health, GitHub status, development plan), and progress recovery after a restart. Failed/interrupted steps stop the goal for attention; they are never automatically retried. This is a limited agent executor, not general-purpose autonomous computer control.

## Priority 5 — supervised autonomy and specialist delegation

The **Goals** tab now provides preview-only fixed recipes and limited
keyword-based safe plan suggestions, followed by explicit owner approval.
Each step is delegated to an allowlisted specialist role and reconciled
with persisted work results. The worker enforces goal approval and specialist
capabilities again at claim time. A goal can be paused, resumed, cancelled
or escalated locally if blocked; already-running tasks finish first.
The dashboard shows daily dispatch limits, step results and audit history.

Limits: five approved steps per goal, eight concurrent active goals, twelve
goal-dispatched tasks per UTC day. These are operational limits, not actual
model-token or monetary accounting. No new paid or model calls are used
for these plans. The existing trusted GitHub status checker may contact GitHub
read-only. A specialist role is not an independent AI runtime.

See [Priority 5 completion and safety guide](docs/PRIORITY5_COMPLETION.md).
**Until authenticated device access exists, the service must remain on
`127.0.0.1` and must not be accessible over a network.**

## Luna’s Design Studio (first self-directed creative assignment)

Open **Development → Luna’s Design Studio** and select **Let Luna redesign ORBIT**. With a configured model connection, Luna receives her current dashboard source and independently produces a saved, reviewable interface redesign proposal, including targeted code suggestions. The proposal is **not** installed or previewed, and no generated code executes. Review the draft before implementing anything. If the model is unavailable, the mission reports an error instead of pretending to finish.

## Current capabilities

- Private localhost FastAPI dashboard and persistent SQLite chat sessions.
- Optional OpenAI-compatible model connection through environment variables.
- Approval-gated memory candidates and project notes.
- **Opt-in memory suggestions**: explicit user statements beginning with “Remember that…” can become pending suggestions; sensitive-looking strings are filtered, repeated suggestions are deduplicated, and approval is required before inclusion in Luna's context. This is a heuristic, not comprehensive privacy protection.
- Durable allowlisted task inbox with a background worker and restart recovery.
- Read-only health/GitHub status checks and self-improvement roadmap proposals.
- Development workshop: drafts **unapplied** code proposals, runs conservative text screening, and can attempt one revision. Saved drafts can be reviewed but are never applied or executed by the workshop.
- GitHub Actions regression checks.

## Verified update and launch

Stop the currently running server first. From the project directory run `bash scripts/verify_and_launch.sh`. The script pulls only fast-forward changes, backs up the default SQLite database, compiles Python files, runs regression tests, and starts Luna **only if the checks pass**. It requires `pytest` to be installed (`python -m pip install pytest`). If you configured `LUNA_DB_PATH` to a custom location, back up that database separately.

## Start locally

Use Python 3.11+ (GitHub CI tests 3.13).

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 on the **same machine**. Keep the bind address at 127.0.0.1: there is **no authentication** for remote users yet.

Configure the model separately using `LUNA_MODEL_URL`, `LUNA_MODEL_NAME`, and `LUNA_API_KEY` in the local environment. Do not commit credentials. SQLite is stored in `luna_local.db` by default; back it up before migrating hosts.

## What is *not* implemented

- Remote phone/iPad access with authentication.
- Arbitrary agent tool use, model-selected actions, real sandboxed code execution, automated patch application or safe self-deployment.
- Autonomous source code changes without review.
- Verified semantic correctness of AI-generated patches.
- Automatic identification of arbitrary conversational memories. Memory suggestions are intentionally narrow and opt-in.

## Development workflow

Development proposals are drafts, not applied changes. The quality gate flags some common issues but **cannot** certify security, functionality, or syntax of unified diffs. GitHub CI validates repository code, not generated draft patches. Routine changes should be batched, reviewed and tested before installing locally.

See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), and [development policy](DEVELOPMENT_POLICY.md).

## Development backlog and overnight delegation (foundation)

The local API now has `GET/POST /agent/backlog` and `GET/POST /agent/overnight`. Backlog items have priority (1 essential, 2 next, 3 later), owner (human/assistant/luna), and an optional **allowlisted** job kind for Luna. Overnight delegation is **off by default**, persists in SQLite, dispatches at most the configured number of jobs per UTC day, and pauses at its configured model-token budget. The worker reconciles completed jobs and flags interrupted dispatches for attention.

Example local-only calls: `POST /agent/backlog` with `{"title":"Check project health","priority":1,"owner":"luna","kind":"project_health"}`; `POST /agent/overnight` with `{"enabled":true,"max_jobs":3,"max_model_tokens":0}`. Zero token cap currently means no token-budget enforcement, **not** zero AI usage. **Model token accounting is not yet connected to provider responses**; do not enable AI-generating unattended jobs until real accounting and request limits are implemented. Current unattended kinds are read-only checks and proposal generation, not code execution or deployment. This is an initial foundation, not an isolated code-writing sandbox, secrets vault, or full overnight autonomous coding agent. Keep the device awake and the worker running.
