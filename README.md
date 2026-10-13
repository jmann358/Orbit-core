## Resuming ORBIT / Luna after a new chat or AI

**POJO RESUME:** Read [the durable project handoff](docs/orbit/RESUME.md), check [the current priority](docs/orbit/STATE.json), and verify GitHub issue [#52](https://github.com/jmann358/Orbit-core/issues/52) before taking action. Completed plans are archived in `docs/orbit/reference/`; do not redo them or treat planned tests as completed.

# ORBIT / Luna — THRONE

Luna runs on THRONE, the Mac M4 mini, as the sole active host and memory writer.
Open **http://127.0.0.1:8000/** on that Mac after login. iPhone/iPad access is
planned but is not connected or authenticated yet. Keep the dashboard local.

## Current version and source

Published app label: **pojo.2**. **pojo.3** is reserved, not released.
The installed Mac candidate is based on draft #57 plus local Mac fixes;
it is ahead of published main. See [current evidence](docs/THRONE_STATUS.md).
Do not run an old main-branch update command over this candidate installation.

## Continue work

1. Read [the full plan](docs/FLIGHT_PLAN.md), [acceptance register](docs/ACCEPTANCE_REGISTER.md)
   and [current status](docs/THRONE_STATUS.md).
2. Review [old/new reconciliation](docs/PLAN_RECONCILIATION.md), then check
   live GitHub main, candidate heads and CI before changing source.
3. Work on the next bounded package; reuse completed work and preserve memory.

POJO THRONE / POJO RESUME are lookup cues, not credentials or automatic memory.
[Issue #52](https://github.com/jmann358/Orbit-core/issues/52) is the public handoff
index; its historical pre-transfer statements are superseded by host evidence.

## Moving and power

Shut down normally before unplugging. At home, power on and log into the same
Mac account; allow startup time, then open Luna. Her local address does not
depend on Wi-Fi. Computer sleep is disabled on power. Automatic restart after
power loss is enabled, but FileVault/login still requires the owner before
Luna resumes. A full reboot and overnight soak remain acceptance tasks.

## Development boundaries

Read [AGENTS.md](AGENTS.md) and [development policy](DEVELOPMENT_POLICY.md).
Run tests only with synthetic databases and isolated test settings. Passing
tests do not authorize release, private-data transfer, paid services or
execution of generated code on the live Mac. Current code proposals remain
unapplied. See [release policy](docs/LUNA_RELEASES.md).

Historical setup commands and detailed feature walkthroughs are retained in
[the earlier README](docs/archive/README-pre-throne.md) for reference only.
They are not instructions to restart the Chromebook or enable another writer.
