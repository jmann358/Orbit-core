# Priority 5: approved goal delegation, phase one

This increment builds on the existing goal and task queue, rather than
adding an unrestricted planning agent.

- A user proposes a goal with one to five **explicit** allowlisted steps.
- Approval of the goal authorizes only those listed, read-only steps.
- The existing worker dispatches at most one unfinished step per goal.
- Dispatching the step and recording its queue job happen in one SQLite
  transaction. Repeated ticks cannot enqueue duplicates for that step.
- Each step has a linked task ID and audit trail. A read-only report gives
  progress, job outcome, attempt count and the next step.
- Owner controls pause, resume and cancel a goal. Pausing prevents the
  *next* step, but does not interrupt an already queued/running task.
  Cancelling prevents future steps and cancels any unstarted queue item;
  an in-flight handler is allowed to finish.
- The persistent global worker pause switch blocks goal dispatch as well.
- A failed or interrupted step puts the goal into `attention`. It does
  not silently retry or continue to the next step.

API (localhost-only):
- `POST /agent/goals`: propose an allowlisted plan.
- `POST /agent/goals/{id}/decision`: approve or reject the entire plan.
- `GET /agent/goals/{id}/report`: inspect step-level progress and blockers.
- `POST /agent/goals/{id}/control`: `{"action":"pause"}`,
  `{"action":"resume"}`, or `{"action":"cancel"}`.

This phase is **not** model-generated task planning or general multi-agent
coordination. It introduces no additional provider calls, shell execution,
credentials, spending, external endpoints, or model-written code application.
It does not permit re-approval of a failed goal; a new reviewed plan is
required. Existing localhost dashboard endpoints are unauthenticated:
do not expose them to a network.

Before wider autonomy, add authenticated user/device access, durable backups,
explicit per-agent capability manifests, and reliable actual provider cost
metering. GitHub CI verifies code but does not verify the local runtime.
