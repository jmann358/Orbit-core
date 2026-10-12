# POJO ENGINE WAVE 2 — host readiness and handoff (2026-10-12)

**Station:** Chromebook/ENGINE. **Next intended home host:** Mac M4 mini.
**Scope:** launch stability, usable local AI, private SQLite continuity, local resource pressure, owner-visible evidence and safe host handoff. This document is planning/evidence only and does not authorize running anything on a personal device.

## Shared version and isolation

- Published `main` is `pojo.2` at `baf96abff8105b89e7b4c924ff03921f084923b5`.
- HELM's consolidated candidate is **draft PR #45**, not merged.
- ENGINE's isolated launch improvement is **draft PR #46**. It changes only `scripts/start_luna_agent.py`, `scripts/luna_mac_service.py`, and the `tests/test_engine_wave2_launch_readiness.py` tests, plus this handoff document.
- ATLAS is responsible for independent security/acceptance reviews. ENGINE must not edit their branches, merge drafts, deploy, change device access, or edit private host data from GitHub.
- A GitHub test pass is source-level evidence, not live Chromebook/Mac acceptance or an installed update. If codeheads move, repeat checks at final exact SHA.

## What has been established

1. Chromebook previously started Luna's localhost dashboard and task worker. A **working model reply was not demonstrated**. The earlier CPU observation dropped from roughly 62% to 21% after the terminal/browser were closed; this does **not** isolate whether the server, model, a polling tab, or another process caused the load.
2. The current project already provides local Ollama discovery, `luna_today.py --check`, `luna_one_time_setup.py --check`, WAL-consistent `luna.database_backup.backup`, guarded startup snapshots and Mac LaunchAgent support. Do not build competing installers/backups.
3. ENGINE #46 adds a bounded **loopback-only port 8000 presence check** *before spawning workers or self-build activity*. It rejects a duplicate attempt and reports occupancy in `--check`. A port listener is not necessarily Luna; this is not an OS-wide lock, and a startup race is still possible.
4. ENGINE #46 distinguishes LaunchAgent **registration** from proof that the service/worker is actually healthy. Honest worker heartbeat/result evidence remains a separate runtime check.
5. Mac auto-start and migration are **unverified on the real hardware**; an existing `luna_local.db` on a fresh Mac must never be described as migrated merely because a new database was created.
6. Dashboard currently binds to `127.0.0.1` and does not provide authenticated phone/tablet access. **Do not expose** it on a LAN, proxy or public tunnel.

## Read-only actions, only when the owner is at the device

On the Chromebook, with Luna stopped or running as already chosen, use only the non-starting inspection:

```bash
cd ~/Orbit-core
git status --short
git rev-parse HEAD
source .venv/bin/activate
python scripts/luna_today.py --check
```

On the Mac, when the source checkout exists, no setup/installation is implied:

```bash
printf 'Architecture: '; uname -m
printf 'macOS: '; sw_vers -productVersion
command -v python3 || true
command -v ollama || true
command -v brew || true
if [ -f "$HOME/Orbit-core/scripts/luna_one_time_setup.py" ]; then
  cd "$HOME/Orbit-core" || exit 1
  git status --short
  git rev-parse HEAD
  python3 scripts/luna_one_time_setup.py --check
  python3 scripts/luna_mac_service.py --status
fi
```

Do not share API keys, private SQLite rows, personal chat messages, machine login names or OS environment dumps in project reports. The currently published `--status` message can falsely imply liveness; its wording fix is only on unmerged ENGINE PR #46.

## Migration / verification sequence — explicit owner authorization before writes

1. Record the actual source database location on Chromebook and stop competing writers or use SQLite's online backup API. Create an **encrypted/owner-controlled** transfer plan first.
2. Make a consistent snapshot including committed WAL changes, check `PRAGMA integrity_check`, and protect the original and every prior backup. Retention choice C: never discard history as a convenience.
3. After owner-approved private transfer, validate the Mac snapshot **before** starting an automatic Luna service or pointing it at the restored database. Keep one authoritative writer and a verified rollback.
4. With the owner present, check a genuine local model completion, not only `ollama list` or model config. The current Mac setup includes a loopback-only inference probe, but that script may install packages, download a model, and register autostart when run without `--check`.
5. Prove the actual app, one explicitly approved fixed mission, receipts after process restart, safe worker state, and Mac login/sleep/wake handling. Then perform a separate authenticated mobile pairing acceptance test only after that feature is built and approved.
6. Do not claim that the trusted subprocess environment is a safe sandbox for model-generated code. That requires independent design and platform-specific testing.

## Outstanding acceptance gates

- Real Mac hardware, storage and permission checks
- Working local inference and acceptable resource usage
- Actual SQLite backup/provenance/restore with no leaked private data
- Reliable Mac LaunchAgent and independent worker evidence after restart
- One authoritative host and controlled Chromebook retirement/rollback
- Approved authenticated iPhone/iPad access, not a raw localhost link
- Owner signoff for merging candidate PRs, releasing pojo.3 or enabling new capabilities

**No device setup, private database mutation, model download, credential permission or release was done by this handoff.**
