## Current Luna version: pojo.2

Luna uses the owner's sequential release labels: **pojo.1 → pojo.2 → pojo.3**.
The current, published app label is **pojo.2**; **pojo.3** is reserved for
the next deliberately approved release, not automatically assigned to a
random Git commit. See `docs/LUNA_RELEASES.md` for the actual release history.

Update the single `VERSION` value in `luna/release.py` when intentionally
cutting a new release. The dashboard, browser title, and `/version` API
read that same value so they cannot drift. The earlier proposed
`1.1.2.3` naming scheme was superseded. Changing the version label
alone does not grant permissions, deploy software, or add capabilities.

## Approve one AI code draft from Luna, not another terminal session

If Luna is already chatting through a trusted configured cloud model (such as
Groq) or an existing local model, you don't need to turn on blanket cloud
developer permissions just to test **one** code improvement.

1. In Chat, say **"Luna, begin improving yourself."** She saves an actual
   health-check job and one bounded development mission, and shows its real ID.
2. Click **Approve one AI code draft** beside that mission (or open
   **Agent Studio**, then find the queued mission and click its approval).
3. Read the displayed model/provider and warning. Click **Confirm** only
   if you explicitly authorize up to **two model requests**, potentially
   billable by your provider, for **that one mission**.
4. Luna's already running background development worker may now draft and
   syntax-check a single allowlisted source replacement, saving an *unapplied*
   diff in **Agent Studio**. Use **Refresh** there to inspect the real result.

This consent expires after **60 minutes** and is bound to the specific
model and endpoint. Changing models, a revoked grant, an expired consent or
a paused worker blocks subsequent work. Calls are reserved *before* sending
a provider request; an interruption does not trigger an automatic replay.
An unused grant can be revoked in Agent Studio. The regular two-attempt
daily developer budget still applies. Consent does not authorize future
missions, new permissions, automatic GitHub writes, merging or deployment.
The API key stays in the host environment, not the consent database.

**A cloud provider's free tier is not a guaranteed price cap.** The owner
must explicitly approve a call that may be billable. The model may return
invalid source or an error; the resulting mission then needs review rather
than claiming success. No connection to this ChatGPT conversation or its
tools is implied.

## Tell Luna to improve herself (real work, not copy-and-paste scripts)

In Luna's existing Chat, say: **"Luna, begin improving yourself."**

This exact everyday phrase now creates two **actual persistent records**:
a project-health task in the existing local worker inbox and an allowlisted
development mission in the existing independent developer worker. Luna replies
with their real IDs. The health check runs without an AI model, while the code
draft needs a separately permitted developer-model connection. This matters:
a connected Groq or other conversational API is not, on its own, permission
to use the same API for potentially billable developer tasks. The response
truthfully identifies blockers instead of promising that a model-free worker
will generate code. GitHub and ORBIT source files remain unchanged until
a separately authorized, verified publication or application workflow.

To ask for actual evidence, say **"What have you actually improved?"** or
**"What's the status of your development?"**. Luna reads the saved mission
status instead of inventing a progress report. **"Luna, run a diagnostic"**
queues the already implemented local project-health checker. If Luna's AI
previously invented a plan and you simply reply **"yes, let's do it"**,
that reply alone does *not* authorize tools or execute code: she now explains
what would be needed to create a real task. After a real work receipt, "yes"
instead reports the work's recorded status, without duplicating it.

Do **not** copy a model-generated shell script that references a guessed
~/orbit directory, an invented /api/health endpoint, or JSON-based approved
memories: ORBIT already has local source inspection and health checking,
and memory proposals are approved in the SQLite-backed dashboard.
No app-generated model text can silently create, run, or deploy new code.

## Let Luna create her own helpers

With the current version running on your Chromebook or Mac, open Luna's
**Chat** and say:

```text
Luna, create a second agent to help you code.
```

Luna will **propose** an actual persisted helper with an explicit, limited
role and show you an **Approve this agent** button inside the conversation.
Approval is not automatic. Once approved, the agent is active and Luna
queues its first real tasks. Go to **My agents** at
`http://127.0.0.1:8000/agents` or say **List my agents** to inspect
what it actually did, its pending tasks, results, and errors.

You can also say **Approve agent 1**, **Pause agent 1**, **Resume agent 1**,
or **Ask Patch to review code** when an agent named Patch is active.
On the **My agents** screen, Luna can make another helper, and you can
approve, reject, pause, resume and assign bounded tasks without opening
GitHub or copying prompts to ChatGPT.

The first supported specialist roles are:

- **Development Helper**: independently performs local project health
  checks and, when a separately enabled agent model is available,
  a real *read-only* code review of an approved ORBIT source module.
- **Project Inspector**: independently checks the project locally,
  without requiring any AI model.
- **Planning Assistant**: uses an explicitly enabled model to produce
  a reviewable development plan. Plans are **not applied or executed**.

The worker processes approved tasks while Luna's local app is running.
Agent definitions, queued tasks, and results are saved in the existing
SQLite database, survive normal restarts, and appear in Luna's
**Waiting for you** and **Luna's work** panels. Pausing the main worker
pauses new helper task claims. Model requests are bounded to four total
per UTC day across these helpers, have no silent retry, and are blocked
until `LUNA_AGENT_MODEL_ENABLED=1` plus a configured model are present.
Cloud model use additionally requires the existing explicit
`LUNA_AGENT_ALLOW_CLOUD=1` setting; no new paid service is enabled.

**What this does not do:** helpers cannot write or install code, access
a terminal or external accounts, provision cloud services, browse the
web, unlock new permissions or run arbitrary model-authored tools.
The existing independent development worker can still prepare bounded
review-only code drafts, but merging and deployment need distinct
permissions. A helper is an isolated task role with real results,
not a separate autonomous computer or a general-purpose
self-modifying agent. The existing localhost-only security requirements
still apply. A Mac backup safety gate also applies to unattended
helper tasks in service mode. No one else's assistance is required for
creating and running these initially supported helper roles, assuming
Luna and the necessary existing AI model are operating locally.

## Start Luna on a Chromebook (simple owner screen)

On the Chromebook where ORBIT is already checked out, **stop any previous
Luna server with Ctrl+C**, then use:

```bash
cd ~/Orbit-core
git pull --ff-only origin main
source .venv/bin/activate
python scripts/luna_today.py
```

Open **http://127.0.0.1:8000** in Chrome **on that Chromebook**.

Luna's opening screen now has one clearly recommended action with a
**Why this?** explanation (also a tooltip on hover), **Waiting for you**,
**Luna's work**, and direct Chat/Design Studio links. Existing technical
sections are available via **More tools** or **All decisions and advanced
tools**, rather than cluttering the home screen. Clicking an item takes
you to its actual saved request or task; no code, memory or approval
is applied on its own. The screen polls local status read-only when visible.

The `luna_today.py` launcher uses an **existing running Ollama model** if
one is detected and starts the bounded self-building worker; otherwise it
still opens the local dashboard, saved chats and approval queue while
clearly saying that real model-backed chat/design generation is unavailable.
If a separately configured AI provider is present, the dashboard may use
it for chat, but the launcher does not turn on unapproved cloud
development calls. **Model configuration is not verified inference.**

No Linux software or AI model is installed by the launcher. It does not
create a public deployment, connect your phone, or bypass owner review.
If the script reports missing packages, run
`python -m pip install -r requirements.txt` in the existing virtualenv
before retrying. For a read-only readiness check use
`python scripts/luna_today.py --check`.

## Design with Luna: generate → preview → approve

Luna can now propose a new **visual appearance** without giving generated code
permission to run. After launching the dashboard with a configured, working
AI model, open **http://127.0.0.1:8000/design**, or use the
**Design with Luna** link on the home screen.

1. Describe your desired layout in ordinary language (for example, "Simplify
   the screen, show fewer navigation buttons, give chat room to breathe").
2. Luna produces a validated proposal; its real dashboard preview renders in a
   **script-disabled iframe**, without changing the currently used design.
3. Say what to change next and generate another proposal to refine it. Press
   **Approve and use this design** only when satisfied, or **Discard**.
4. **Restore original layout** undoes the active design. Previous approved
   designs remain locally available to restore.

These are safe appearance tokens: colors, dashboard width, spacing, corner
roundness, and focused/full navigation. Focused navigation keeps the omitted
tabs reachable through **More tools**. Luna cannot add arbitrary widgets,
rearrange the underlying HTML, execute generated code, change app functionality
or install source patches via this studio. The older text-only
**Luna's Design Studio** in Development remains an unapplied code proposal
path for more extensive redesigns.

Design records live in the same local SQLite database as the app and follow
its backup and host-lifetime rules. Model generation uses the existing configured
chat model, so configured cloud providers may receive the design instructions
and existing approved context and may incur their normal usage charges.
Nothing is sent to GitHub. The interface remains **localhost-only** with no
remote login. The preview is visual rather than a functional browser test;
verify interactions after approval. All designs are reversible without
editing source files.

## Mac mini: one-time Luna handoff

For the intended always-on **Mac M4 mini**, once you have the approved
repository checked out, open Terminal there and run:

```bash
cd ~/Orbit-core
python3 scripts/luna_one_time_setup.py --enable-draft-prs
```

The `--enable-draft-prs` flag is the **explicit one-time GitHub
authorization** for Luna to publish draft improvement PRs. It uses the
GitHub CLI's own login/keychain store; no GitHub token is written to ORBIT's
source, configuration or logs. If GitHub authorization is missing, the setup
opens the normal web login flow. The CLI may request the broader GitHub
`repo` OAuth scope, so only authorize that scope if you accept it. Luna's
publisher itself is restricted to `jmann358/Orbit-core`, draft PRs, and
six approved low-risk source files; she cannot self-merge or deploy.

For **local-only autonomous drafts without GitHub write access**, omit the
flag: `python3 scripts/luna_one_time_setup.py`.

This installs only local free software: a project Python environment and its
declared Python dependencies, Ollama through **existing Homebrew** when needed,
and a local coding model if no code-capable model is already installed. It then
creates a private macOS LaunchAgent that starts Luna's chat and independent
developer worker automatically when you log in, and restarts them after a
process failure. **No model API charges, cloud account, public listening port, self-merge or
deployment are enabled.** GitHub draft PR permission is enabled only with
`--enable-draft-prs` and successful owner authentication.

The setup may download multiple gigabytes of model files; ensure sufficient
storage. Without Homebrew or the Ollama Mac app installed, the script explains
the missing one-time prerequisite. It does not create or manage a new
Homebrew installation. To inspect prerequisites without changing anything:

```bash
python3 scripts/luna_one_time_setup.py --check
```

After successful setup, on that same Mac open
`http://127.0.0.1:8000` and
`http://127.0.0.1:8000/agent/studio`. Luna schedules one bounded
development draft per day across six bounded, reviewed source modules.
If GitHub drafting was authorized she can publish each successful proposal
as a review-only draft PR. Keep the Mac logged in and awake: a LaunchAgent is
not a system-wide service during logout/sleep. Changes she drafts are kept
for owner review; she still cannot merge, execute, deploy, or grant herself
GitHub credentials. Phone access requires a separate owner-approved secure
pairing/transport setup.

```bash
python3 scripts/luna_mac_service.py --status
python3 scripts/luna_mac_service.py --uninstall
```

Uninstalling the autostart service preserves Luna's database, backups and
model files.

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
