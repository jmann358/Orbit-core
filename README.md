# ORBIT · Luna

ORBIT is a local-first, provider-independent assistant ecosystem. Luna is its conversational coordinator.

## Fastest self-building start (local model, no API subscription)

If Ollama is **already running** on this computer and has a downloaded model,
start Luna's dashboard, local model-backed developer agent and independent
worker together:

```bash
cd ~/Orbit-core
git pull --ff-only
source .venv/bin/activate
python scripts/start_luna_agent.py --self-build
```

Open `http://127.0.0.1:8000` on **that computer**, then say
**"Luna, start building yourself!"** in chat or use the Agent Studio button.
The worker can independently draft one curated improvement per day, within
the existing two model attempts per UTC day. The chat window can close while
the worker continues, but **the computer and launcher must stay running**.

The self-build command first creates a private, integrity-checked SQLite snapshot if a memory database already exists. If that backup fails, it refuses to start unattended development. The read-only `--check` reports whether an existing local Ollama model is visible without revealing model names or secrets.

The launcher automatically discovers an existing Ollama model, preferring
a code-specialized model. It never installs Ollama, downloads a model,
exposes a port, sets up paid services, or supplies a GitHub token. If no
Ollama server/model is available, it exits with a clear message. GitHub
PR auto-publishing is separately disabled until the owner explicitly
configures scoped permissions and enables it. All generated code remains
unapplied, with owner review required.

This is **not** a hosted iPhone-accessible deployment, full unattended
test/repair/merge cycle, or unrestricted source-code agent. If the command
reports missing local model prerequisites, those must be installed and
started on the intended always-on computer first.

## Luna chat + independent agent (integrated preview)

Run both the conversational app and the persistent background worker with one local command:

```bash
cd ~/Orbit-core
source .venv/bin/activate
python scripts/start_luna_agent.py --check
python scripts/start_luna_agent.py
```

Talk to Luna at `http://127.0.0.1:8000`; inspect her real development
missions at `http://127.0.0.1:8000/agent/studio`. Model use requires an
explicit local configuration. Proposals are saved for review, not executed.
Nothing in this repository is a running cloud deployment. See
[Agent documentation](docs/LUNA_DEVELOPER_AGENT.md) and
[Cloud readiness](docs/CLOUD_FIRST_FOUNDATION.md).

## Start Luna now (local preview)

On the computer where the repo is checked out, activate its Python virtual environment and run:

```bash
cd ~/Orbit-core
source .venv/bin/activate
python scripts/start_luna.py --check
python scripts/start_luna.py
```

Then open **http://127.0.0.1:8000** on that computer. The check reports missing packages and whether model configuration is present **without displaying keys**. Install missing packages with `python -m pip install -r requirements.txt` if necessary. The launcher doesn't pull code, install anything, start cloud calls, or change network access. It launches the existing dashboard; it is **not** authenticated iPhone/iPad access. Chat model-backed replies still require a configured working provider, and local-only access must remain on `127.0.0.1`.

## Luna local release: what is actually usable

The localhost preview opens on Luna's **Chat** screen. A read-only connection
banner makes it clear whether a model is configured; this is not a live
provider health check. Full chat transcripts remain in local SQLite, while
model prompt history is deliberately bounded. Saved conversations display a
recognizable preview instead of an anonymous number. Setup and transport
errors are shown as notices, not model-authored assistant messages.

**Launch on the computer, not the iPhone:**

```bash
cd ~/Orbit-core
source .venv/bin/activate
python scripts/start_luna.py --check
python scripts/start_luna.py
```

Open http://127.0.0.1:8000 on that same computer. This launches the UI only;
a model-backed reply requires a separately configured model, and the
connection indicator only verifies settings, not provider uptime.

For an **already-running local OpenAI-compatible server** on the same
computer, configure its real model name and endpoint before launching Luna.
For example, if an Ollama-compatible server is already running on loopback:

```bash
export LUNA_MODEL_URL=http://127.0.0.1:11434/v1
export LUNA_MODEL_NAME=YOUR_INSTALLED_MODEL_NAME
python scripts/start_luna.py
```

No local model is installed by this launcher. An HTTPS model requires a
supported provider and an API key set locally, not in GitHub. Cloud models
may incur charges, and personal chat text is sent to the selected provider
when you use one. Do not connect paid services without approval.

**Release verification:** GitHub Actions tests the chat API, simulated local
model round trips, history persistence across reopened clients, configuration
safety, and Python syntax. Actual on-device launch, working model connection,
and full iPhone access remain unverified until tested on those devices. This
release does **not** enable remote access, microphone, external accounts,
autonomous code deployment, or provider spending.

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

Stop the currently running server first. From the project directory run `bash scripts/verify_and_launch.sh` **only when online**. The script verifies GitHub Actions CI for both the current checkout and a **pinned remote `main` revision before importing Luna's modules or checking out updates**. It then creates a private SQLite-consistent snapshot of the configured `LUNA_DB_PATH`, fast-forwards only to that preverified SHA, and rechecks it before starting Luna on localhost. It intentionally does **not** execute newly fetched test code using your local memory database or API credentials. If the public GitHub CI check cannot be reached or has not passed, launch refuses to proceed. The update path also pins the reviewed CI workflow's Git blob; changing the CI workflow requires a separately reviewed update rather than automatic installation. Ordinary `python scripts/start_luna_agent.py --self-build` remains the separate local developer-worker startup path; neither launcher installs Ollama or provides phone access.

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
