# Pojo.3.1.0 — Mac M4 mini first-session handoff

This is a **read-only preparation and acceptance checklist**, not a request
to install, deploy, pair devices, merge code, or migrate private memory now.

## Ownership and current software

- GitHub default branch remains `main`, application version `pojo.2`.
- Draft changes for the next Mac-flight candidate are tracked in PR #38 and
  its focused supporting PRs. A draft pull request is NOT an installed update.
- Pojo.3.1.0 is the owner coordination checkpoint, not an automatically
  published application version.
- Existing Chromebook data is authoritative until the owner verifies a
  WAL-consistent backup, controlled transfer and integrity-checked Mac restore.
  Never create a new persistent Mac database and silently call it migrated.

## Phase A: non-mutating terminal evidence, when physically at the Mac

```bash
printf 'CPU: '; uname -m
printf 'macOS: '; sw_vers -productVersion
printf 'Python: '; command -v python3 || true
printf 'Git: '; command -v git || true
printf 'Ollama: '; command -v ollama || true
printf 'Homebrew: '; command -v brew || true
if [ -d "$HOME/Orbit-core/.git" ]; then
  cd "$HOME/Orbit-core" || exit 1
  git status --short
  git rev-parse HEAD
  python3 scripts/luna_one_time_setup.py --check
  python3 scripts/luna_mac_service.py --status
else
  printf 'No ~/Orbit-core checkout found. No changes made.\n'
fi
```

The `--check` flag reports prerequisites only. The service `--status`
flag inspects the existing service. **Do not run the non-check setup or
service install commands in the first diagnostic phase.** Do not paste
private SQLite contents, access tokens or provider credentials into chat.

## Phase B: recovery state (requires access to existing Chromebook)

1. Inventory the existing SQLite path, any WAL/SHM companions and backup
   locations on the Chromebook without reading personal content into chat.
2. Stop all active writers or use SQLite's online backup API to produce a
   transactionally consistent snapshot. Simply copying an active `.sqlite`
   file may omit WAL transactions. Preserve the original and backups.
3. Verify snapshot integrity (`PRAGMA quick_check`) and the necessary
   schemas, row counts and allowed size ranges offline. Never publish
   personal data, tokens or memory to GitHub or ChatGPT.
4. Transfer only through an explicitly chosen encrypted, owner-controlled
   mechanism. Do not invent a synced cloud location or public URL.
5. Recheck the destination path and verify Mac restored snapshot integrity
   **before** changing `LUNA_DB_PATH` or starting automatic jobs.
6. Ensure there is only one active authoritative writer; retain a rollback
   point and allow older histories to remain intact (retention choice C).

## Phase C: Mac local verification (explicit owner approval required)

- Confirm a supported Python virtualenv, trusted reviewed requirements and
  local model server (Ollama) are available. Real inference requires a
  completed chat request, not just installed model tags.
- Check the local app's `/chat/readiness`, a genuine owner conversation,
  approved goal creation, worker heartbeat, approval, step execution, result
  receipt and persistence across restart. Confirm actions are accurately
  described as worker-reported versus independently verified.
- Verify launch agent service behavior after login, process restart and
  normal machine sleep/wake, with logs and safe interrupted-job recovery.
  The Mac cannot perform unattended work while genuinely powered off.
- Keep HTTP strictly on `127.0.0.1`. The unauthenticated current dashboard
  **must not** be exposed to Wi-Fi, tunnels or the public Internet.
- Authenticate and revoke phone/tablet pairing only after the separate
  architecture is owner-approved and real-device-tested.
- Secure generated-code execution/repair/rollback needs its **own**
  platform-specific verification; current routine-test subprocesses do
  not create an untrusted-code sandbox.

## Required handoff outcome

Produce a pass/fail evidence table with exact revision, Mac setup state,
SQLite integrity and provenance (not contents), model reply evidence,
sequential mission receipts, observed worker status, restart recovery,
consent gate and unresolved blockers. Do not mark a launch complete because
a GitHub CI suite is green.

**Owner approval gates remain intact:** no automatic merge, deployment,
software install, account/device access expansion, spending, credential
connection or publication of the reserved `pojo.3` release.
