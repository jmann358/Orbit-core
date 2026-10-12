# Luna pojo.1 — observed behavior and verified repairs (2026-10-12)

## User observations

- Luna's chat frequently offers a "yes/no" authorization without creating a real saved action.
- A created helper's code-review/plan task remains **queued — Waiting for model configuration**, even when normal chat through an external provider works.
- Clicking **More tools** appears to do nothing.
- Approval requests and model permissions are scattered across tools.
- The home screen and AI conversation contain too much nonfunctional filler.
- Luna invented commands `orbit restart-model` / `orbit reload-model`, endpoint `/api/tools?visible=true`, file `frontend.js`, and `orbit.yaml`. None exist in this repository.

## Root causes confirmed from source

1. `luna/custom_agents.py` gates model-backed helper tasks through `luna.developer_model.configuration()`, which intentionally requires explicit developer-model authorization distinct from normal chat.
2. `luna/focus_ui.py` previously hid advanced navigation using a more specific CSS rule marked `!important` than its open-state rule, so flipping the `orbit-more-open` class could not reveal the buttons.
3. Pending approvals existed under various persisted SQLite stores and independent screens. The visible Approvals category included a task inbox but not the full set of owner decisions.
4. Chat model text is not an executable ORBIT tool invocation. Generic consent in a conversation cannot safely authorize unrecorded model-created promises.

## Changes

- Fixed More tools open-state specificity, visibly opens native advanced controls, and made the Approvals category a permanent top-level tab, even when a focused theme is active.
- Consolidated actual waiting decisions by risk and category under `GET /approvals/pending`. The tab shows one-click safe actions and explicit confirmation only for sensitive choices such as private memories, cloud model requests, and approving delegated goals.
- Added `luna/helper_consent.py`: a previously configured provider may service **one explicitly approved queued helper task** without globally enabling automatic model use. The grant is limited to one call, one specific task, one endpoint/model, expires in one hour, and is consumed inside the worker's claim transaction before any model request. The existing four-per-day helper limit still applies.
- Updated My agents with truthful model readiness and direct one-task model approval.
- Simplified the home heading and tucked advanced worker controls into disclosure. Added model-grounding instructions to Luna's AI prompt to reduce speculative diagnoses, repetitive yes/no questions, and invented repo paths.

## Preserved boundaries

- No existing unapproved model calls are enabled, no provider secrets are placed in SQLite/GitHub/browser state, and cloud use requires an explicit per-task warning that charges may apply.
- Helper model calls remain isolated from personal memories and lack shell, installation, external account, unrestricted files, or deployment privileges.
- A successful API configuration check is *not* evidence that a live provider call succeeded. The repository tests use a mocked provider. Actual Chromebook/Luna startup must be verified on the owner's host.
- Approving a proposal is not approval to install generated code. No changes are automatically applied or merged by Luna.

## Verification

Regression tests cover actual SQLite approval records, confirmed risk categorization, no side effects on mere inbox reads, one-call helper model execution against a mocked HTTP provider, expiry, unauthorized remote access, original dashboard element IDs, and JavaScript syntax. GitHub CI must be green on Python 3.11 and 3.13 before merge.

## Next owner test after `git pull`

Start Luna using `python scripts/luna_today.py`, open `http://127.0.0.1:8000`, and verify that **Approvals** is visible and **More tools** reveals navigation. Under **My agents**, queued AI-backed tasks offer one-time authorization using the model already configured for chat, when supported. Approve a *single* desired task; check for its real saved result. If it fails, preserve the exact error and do not paste API keys into conversations.
