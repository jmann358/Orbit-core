> **Historical station evidence.** Station assignments and pre-Mac status are superseded by [THRONE status](../THRONE_STATUS.md) and [the active plan](../FLIGHT_PLAN.md). Retain the source/test evidence below; do not restart another station or memory writer.

# ENGINE Wave 2 — owner-safe host diagnostics

This focused read-only tool is intentionally **not** a Luna starter or a model smoke test. It does not install, change, stop, activate or repair anything; it does not read conversation history, backup SQLite, log process arguments, print credentials, send cloud traffic or change network exposure.

## Command (after the approved code has actually reached the device)

```bash
cd ~/Orbit-core
python3 scripts/luna_host_diagnostics.py --check
```

You can run it once with Luna open, again after exiting Luna, and compare the five CPU categories. It reports a single local `ps` snapshot for recognized processes (dashboard, worker, launcher, Ollama and visible browser). It **never prints raw command lines**. On ChromeOS Linux, the Chrome browser outside Crostini may not be visible, so zero visible browser CPU does not mean Chrome is inactive. Likewise, a Python process that doesn't match the known launch commands may be omitted. Host OS CPU percentages can exceed 100% across cores when aggregated.

The local loopback dashboard port probe checks for **any listener**, not Luna identity or worker health. The local Ollama `/api/tags` probe only counts advertised models. Neither proves an actual inference reply, nor activates one; the diagnostic always reports `actual_model_reply_verified: false` and `mac_service_liveness_verified: false`.

## Interpreting the user's Chromebook CPU observation

CPU previously fell after closing the terminal and browser, but that sequence alone does not establish which of the dashboard, web browser, worker, local inference, Linux container or unrelated system activity accounted for the load. Compare before/after outputs locally without pasting process commands or secrets into GitHub. If all Luna categories are near zero but ChromeOS CPU remains high, use the Chromebook's own OS task manager; it sees components hidden from the Linux container.

## Still requires physical host/owner evidence

- Real Mac M4 inference completion and idle/active CPU data
- WAL-consistent original Chromebook SQLite backup, consented protected transfer and verified Mac restore
- Exactly one authoritative private database writer across devices
- Mac service login/restart/sleep/wake evidence and worker receipts
- Authenticated mobile pairing and independent approval before any network exposure
- Independent verification and explicit owner permission for release or merge

This is a separate additive ENGINE follow-up on the already staged combined candidate, not an edit to earlier ENGINE #46, HELM #48, HELM #51, HELM #53 or ATLAS branches. Running new code on devices still requires retrieving an approved version; a passing GitHub draft is not an installed update.
