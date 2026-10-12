> **Historical station evidence.** Station assignments and pre-Mac status are superseded by [THRONE status](../THRONE_STATUS.md) and [the active plan](../FLIGHT_PLAN.md). Retain the source/test evidence below; do not restart another station or memory writer.

# ATLAS — Mac-first source security fixes (review only)

**Date:** 2026-10-12. **Target:** exact ENGINE candidate `0b117439567062231f1e003270c1bbf05f86b66a` (#56), not published `main`. This is a separate ATLAS branch. No one has approved a main merge, installation, model provider charge, owner-memory transfer, remote exposure, or release tag.

## What this branch changes

1. **P1 — /chat sensitive intake before storage.** `app.py:/chat` now invokes `luna/sensitive_intake.screen` before `add_message`, memory-suggestion routing, agent commands or model requests. Obvious credentials, bearer tokens, PEM private-key markers and formatted US SSNs are blocked without saving their contents or returning excerpts. Existing regular conversations continue. This is **high-confidence regex screening, not comprehensive PII detection**, secure quarantine, automatic secret revocation or a protected vault. Other intake surfaces and user-controlled cloud history need separate treatment.
2. **P1 — local browser-origin and Host constraints.** The existing middleware now rejects Host-header rebinding outside loopback, cross-origin Origin/Referer values, and cross-site Fetch Metadata headers before handling endpoints. Same-origin localhost browser controls and existing programmatic local clients work. This does **not** create owner authentication: originless API clients are still admitted on loopback, and the app must never be bound to the LAN/tunnel/public internet without a separately approved authenticated/revocable pairing design.
3. **P1 — deterministic shutdown and no recovery race.** The two FastAPI worker threads are signalled, joined, and checked before shutdown is reported complete. If a previous thread remains alive while stopping, a new startup refuses to recover its jobs over an active writer. The worker can still be blocked by a very slow external handler, in which case shutdown fails visibly rather than silently abandoning the thread.
4. **P1 — connection closure.** `luna/cloud_worker.connect` now uses a managed transaction scope with an unconditional connection close, including failed authorization transactions; the existing queue and `luna/mission_consent.py` callers already use `with connect(path)`. No database migration or deletion.
5. **P2 — intermittent CI temporary-directory race.** A new real TestClient lifecycle test uses disposable SQLite paths, waits for both worker threads to stop, and repeats startup/shutdown. The earlier one-off `test_luna_product_release.py` failure involving a not-yet-empty temp directory should not be dismissed based solely on a rerun. Run independent full CI twice and inspect any recurrence; CI races cannot be proven absent by a single green run.

### Verification

Tests are in `tests/test_atlas_mac_first_security.py` and use only synthetic data, local TestClient, mock network interactions and disposable SQLite. No Chromebook or Mac processes or databases were accessed. Exact-head full CI results must be added to the PR after GitHub finishes.

**Release-security trust:** Keep the reviewed `.github/workflows/orbit-checks.yml` byte-identical to the pinned blob `3c13b96eb6a07782be68bf1e233eb6cdae7b048d`. Do not relax or re-pin `scripts/verify_and_launch.sh` simply to make a release pass.

## Mac first-flight approval is a different gate

A green PR establishes *reviewable source*, not that the Mac is operational. Before authorizing an installation/cutover:
- Mac M4: verify Python + environment, disk/capacity, actual local inference reply, bounded CPU and pause/recovery behavior on the real device.
- Verify one authoritative personal SQLite source, owner-approved consistent backup, protected transfer and integrity-tested Mac restore, with rollback and no parallel writer. Never send SQLite or secrets to GitHub.
- Confirm the launch guard validates the exact release commit and trusted workflow; all chosen cumulative branches are integrated **once** and reviewed, not blindly merged as stacked PRs.
- Check real browser/mobile behavior, Mac service login/sleep/wake/restart, lossless message retention, supervised mission-to-receipt and safe handling of interrupted jobs.
- Keep web traffic bound to `127.0.0.1`. Phone/tablet access requires authenticated sessions, transport protection and revocation, not just a working localhost dashboard.
- Secure model-generated code execution, adaptive autonomy, externally verified results and spend enforcement are future features and remain unverified.
- Owner must separately approve any main merge, release/tag, launch, device access, model download/provider payment and personal-data cutover.

## Handoff

**HELM:** Review new source/negative tests independently, including local-client compatibility and lifecycle behavior, and propose a single cumulative reviewed merge path only with owner authority.

**ENGINE:** Continue hardware/diagnostics only; do not edit these files concurrently or use the live Mac/Chromebook to certify GitHub code. Do not duplicate source tests or create another SQLite store.

**ATLAS:** Keep this PR draft and report exact full CI outcomes and unresolved problems; never call the Mac ready based solely on source CI.

**Source of truth after a long gap:** Issue #52 POJO RESUME plus live GitHub refs/CI, not assumed chat synchronization.
