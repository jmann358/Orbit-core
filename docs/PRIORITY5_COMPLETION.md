# Priority 5: supervised autonomy and delegation — completion candidate

## What is implemented

Priority 5 establishes a complete **bounded supervised delegation workflow**
for ORBIT's three existing low-risk specialist capabilities. This is *not*
general autonomous computer use or independent AI agents (those are separate,
later priorities).

1. **Plan:** Enter an objective, select explicit fixed actions, or choose one
   of the deterministic goal recipes. Preview recipes without side effects.
   Arbitrary objective text is kept as data, not converted to commands.
2. **Approve:** The user reviews the exact action sequence. Nothing is
   scheduled until the user explicitly approves it. No plan can change the
   capability registry.
3. **Delegate:** The coordinator assigns each sequential step to the declared
   inspector, researcher, or planner role. Dispatching a step and linking its
   job are one SQLite transaction (no partial dispatch or double scheduling).
4. **Enforce:** The worker checks the linked goal's approval state,
   specialist capability, step kind, and dependency ordering at claim time.
   A paused goal's queued jobs wait; revoked or corrupted approvals are
   quarantined for review. Standalone trusted maintenance jobs remain
   independently allowlisted.
5. **Bound:** At most five steps per goal, eight concurrently approved/active
   goals, and twelve delegated job dispatches per UTC day. A full daily
   budget or queue defers work until capacity returns. No new provider calls,
   shell execution, code application, permission grants, new external services
   or spending are introduced.
6. **Observe:** Per-goal progress, timestamps, step-to-job links, job outcomes,
   attempt counts, and an append-only local goal event history are available
   through API and dashboard.
7. **Stop:** Pause, resume, cancel and global worker pause persist. Pausing
   prevents future claims from queued goal steps; an already-running handler
   is not killed. Cancel prevents pending work and cancels unstarted tasks.
8. **Recover:** Failed, interrupted or unauthorized steps stop the goal
   for owner attention. No blind rerun or skipped dependency. One deduplicated,
   locally stored owner request is generated per blocked goal. Retrying an
   individual failed child job cannot bypass goal review. A new plan requires
   separate user approval.

## API (localhost-only)

| Endpoint | Purpose |
| --- | --- |
| `GET /agent/goals/recipes` | Inspect fixed recipes |
| `POST /agent/goals/recipes/preview` | Preview `{"recipe_id":"development-review","objective":"Review ORBIT health"}` |
| `POST /agent/goals/recipes/propose` | Create an unapproved goal from the selected recipe |
| `POST /agent/goals` | Create an unapproved goal from explicit steps |
| `POST /agent/goals/{id}/decision` | Approve/reject the immutable step list |
| `GET /agent/delegation/status` | Read daily/active delegation budgets |
| `GET /agent/goals/{id}/report` | Inspect progress, audit events and blockers |
| `POST /agent/goals/{id}/control` | Pause, resume or cancel |
| `GET /agent/specialists` | Show static bounded specialist capabilities |
| `GET /agent/jobs/{id}/events` | Inspect trusted worker job events |

The **Goals** dashboard includes fixed recipes, previews, specialist and job
progress, budget status, pause/resume/cancel controls and on-demand audits.

## Safety and limitations

- The dashboard has **no authentication**. Bind **only** to
  `127.0.0.1`; never expose it on Wi-Fi, the internet or a tunnel.
  Authenticated device pairing is a *future* security milestone, not in this PR.
- Role routing delegates to existing trusted functions, **not independent
  model processes**. No model-generated plans or real agent-to-agent
  communication. Priority 7 is where true specialized model agents belong.
- The job handlers' existing network behavior is unchanged. The GitHub
  status checker can perform its preexisting read-only GitHub request.
- The 12-per-day limit counts **dispatched jobs**, not usage or monetary costs.
  It is not a cloud token/spending cap. No new model calls are made.
- A paused goal stops future queued claims; a job already running must finish.
  The worker's existing request timeouts remain its per-operation bound.
- Restart recovery does not replay a running job. Re-approve via a *new*
  plan after inspecting attention-state failures.
- Stored SQL database records are not protected against someone with
  privileged filesystem access who intentionally edits SQLite. Real OS
  access controls and authenticated remote sessions are separate milestones.

## Acceptance checks

The GitHub CI suite tests user approval gates; recipe validation; role
assignment; daily and active limits; concurrent advancement; atomic task
dispatch; step sequencing; pause/resume/cancel; tampered job kind and goal
status denial; interruption recovery; manual retry restrictions; local
deduplicated owner escalation; and dashboard/API contracts.

**Before operating locally:** stop the old server, back up the SQLite
database, pull the approved and merged code, run regression tests, and
restart on `127.0.0.1`. See `scripts/verify_and_launch.sh`. CI passing
does not prove the host's Python environment, configured credentials, or
hardware works correctly.

## Exit criteria for Priority 5

- [x] Durable approval-gated bounded goals and specialist routing
- [x] Pre-execution capability enforcement and budgets
- [x] Observable progress, outcomes and persistent audit
- [x] Explicit owner interruption controls and safe restart handling
- [x] Local escalation of blocked work, without repetitive requests
- [x] UI and API to preview, approve and inspect
- [ ] Post-merge CI on `main` and local device smoke test (after approval)

Future work (not part of Priority 5): authenticated Mac/iPhone access,
provider-independent model agent runtimes, semantic AI task decomposition,
actual provider metering, strong sandbox boundaries and deployment security.
