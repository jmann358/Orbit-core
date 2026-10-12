# Luna Developer Agent — first runnable autonomous loop

**Status:** source implementation awaiting CI and device verification. No cloud service
has been created. No model account or paid service has been connected here.

Luna is no longer limited to a chat answer or a static "next steps" list in this
branch. An independent worker can take a *durable development mission* from SQLite,
read one allowlisted source file, request a real candidate replacement from a
separately configured model, validate the candidate's exact base revision and Python
syntax in a disposable workspace, and persist a reviewable diff and full replacement.
The worker can keep running after the browser closes, provided its host stays on.

The **Agent Studio** is at `http://127.0.0.1:8000/agent/studio` once the app is
running locally. It lets the owner queue bounded development missions, inspect
real proposals, and pause future development claims. Already-running work is not
cancelled by Pause.

## What a successful agent mission produces

- A named source target, base SHA-256, and validated replacement SHA-256.
- A complete candidate source file and unified diff stored in SQLite.
- A fingerprinted, revision-locked review manifest.
- A review state in Agent Studio; owner can assess before any publication.
- Model-attempt counting with at most **2 attempts per UTC day**, counted before
  making requests; failed requests also count and are **not auto-retried**.
- On interruption or invalid code, attention instead of silent success.

**No generated code is executed, committed, merged, deployed, or installed.**
Full tests must run later in an approved isolated environment. "Syntax valid"
never means "safe" or "correct". Luna cannot change her own permissions.

## Safe local preview

Use the already established project virtual environment and start the web
server via the standard Uvicorn command on loopback:

```bash
cd ~/Orbit-core
source .venv/bin/activate
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/agent/studio` on that same computer.

A model-free diagnostic checks the worker without starting it or touching
the database:

```bash
python scripts/cloud_worker.py --check
```

You can create a mission in Agent Studio with no model configured; it will
stay queued and won't initiate any model request until owner opt-in and the
worker are enabled.

## Enabling a model-backed local development session

**Only when a compatible local inference server and a model are already
running on the same machine**, configure the existing provider independently.
Replace the placeholder with the actual model installed on the host.

```bash
export LUNA_MODEL_URL=http://127.0.0.1:11434/v1
export LUNA_MODEL_NAME=YOUR_INSTALLED_MODEL_NAME
export LUNA_AGENT_MODEL_ENABLED=1
export LUNA_AGENT_AUTO_ENABLED=1
export LUNA_WORKER_ENABLED=1
python scripts/cloud_worker.py
```

The cloud worker will queue at most one curated improvement per UTC day.
It picks a fixed allowlisted source target and stages a proposal without
execution. This process survives closed browsers but **not host shutdowns**;
hosting must be separately provisioned for 24/7 availability.

Cloud models are **explicitly off for developer tasks**, even if Luna chat is
configured to use one. To permit a specific already-authorized cloud provider,
the owner would separately have to supply `LUNA_API_KEY` locally and set
`LUNA_AGENT_ALLOW_CLOUD=1`. Provider charges may apply. This call-count limit
is **not** a monetary budget or a verified token limit. No purchases, remote
provider keys, account setup, or cloud calls were performed in this PR.

For one bounded task instead of a continuous worker:

```bash
python scripts/cloud_worker.py --once
```

## Current scopes and protections

- Current replacement allowlist: `luna/development.py` and
  `luna/self_improvement.py`. Editing `app.py`, credentials, policies,
  network authentication, host deployment, or arbitrary files is forbidden.
- No subprocess, generated code evaluation, arbitrary tool calling, or
  changes outside temporary staging. The worker only invokes its fixed
  registered handlers.
- No personal conversation logs are sent to the developer-model adapter.
  It uses only explicitly allowlisted project source and the scoped task.
- No replay of development work on lease expiry (avoids repeat model charges).
  The durable mission and worker statuses can be inspected after a restart.
- Owner pause blocks new developer work but not existing read-only heartbeats.
- No hidden ChatGPT model-to-model bridge, no automatic PR merge, no bot
  credentials, no outbound GitHub access from the agent.

## Integrating ongoing Codex and cloud work

This agent branch is **stacked on PR #14**, the cloud worker foundation.
Codex's **PR #13** contains separate chat reliability work, while **PR #12**
contains the conversation-first local launch and persistence improvements.
The agent implementation reuses the cloud worker and adds a small router
registration in `app.py`. All PRs need integration conflict review and CI
together before merging or launching on a shared host. Don't discard Codex's
fixes or treat passing tests on isolated branches as integrated release proof.

## Finish-line requirements not silently bypassed

1. Verify an actual model-backed development mission on the target runtime,
   not just mocked tests and local static checks.
2. Reconcile PRs #12–#14 and this branch; re-run real browser, model, and
   restart persistence acceptance tests.
3. Implement a genuine authenticated mobile login and secure reverse proxy.
   The temporary bearer gate is **not** an iPhone browser login.
4. Add persistent encrypted backup/restore testing, owner notification,
   subscription/cost controls, and a suitable isolated code test pipeline.
5. Get explicit owner approval before creating an always-on host or enabling
   a paid service, network exposure, code installation or model-generated
   code publication.

This moves Luna from a simulated agent catalog to a **bounded, real agent
developer loop** without pretending the complete autonomous product is live.
