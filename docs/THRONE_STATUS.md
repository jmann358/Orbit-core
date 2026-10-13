# THRONE — current status and next gate

October 12, 2026. One Mac host, one authoritative memory writer.
This page supersedes historical station/setup status; it does not authorize
paid calls, expanded access, automatic code application, merging or releases.

## Revision boundaries

- Published main: pojo.2, baf96abff8105b89e7b4c924ff03921f084923b5.
- Latest remote candidate: draft #57, fe9ef11c1de76d3f5c6aa9d2905c0c3feefa461b;
  exact-head CI runs 38302199905 and 38302165208 succeeded.
- Installed Mac: ee067a390914c03bfc189bb8dfedf0f7bb59061e; 492 tests passed,
  13 warnings during setup. Actual chat, health job 27 and persistence across
  service restart were observed. No full reboot or power-loss test performed.
- New source work: fix/throne-plan-and-worker-transactions, based on ee067a3.
  This review branch is separate from the installed service. Final candidate
  test evidence and preservation checkpoint are recorded below when complete.

## Completed in the first reconciliation package

- New and recovered old requirements aligned in FLIGHT_PLAN.md,
  ACCEPTANCE_REGISTER.md and PLAN_RECONCILIATION.md.
- README/roadmap now point to one active plan. Obsolete station/setup/cloud
  documents archived with replacement pointers; history retained.
- Worker transaction failure reproduced: ordinary writes persisted despite
  exception. Deferred DML transactions restore rollback; explicit immediate
  reservations precede developer setup writes. Four regression scenarios cover
  implicit/explicit rollback, successful commit and interrupted mission enqueue.
- Targeted worker/consent/developer checks: 53 passed. No live memory used.
- Launcher unit tests now model their port state explicitly; running the
  owner's Luna no longer prevents them reaching their fake launch/backup paths.
  Dedicated occupied-port refusal tests remain unchanged.

## Operational limits

Local Ollama is configured with cloud disabled. Services bind loopback only.
Private memory was transferred with owner permission; Chromebook originals
remain preserved and stopped. Mac disk encryption is enabled. The temporary
transfer listener is closed. Automatic login services and service recovery
work; sleep is disabled on power and automatic restart after power loss is
enabled. The owner must unlock/log in after boot before Luna resumes.

The installed version still has the recorded drafting failure; the source
candidate passes one local drafting scenario, as recorded below. No Mac sandbox, secure mobile pairing, independent backup of later Mac changes,
complete self-development loop or newly published pojo.3 is claimed.

## Next gates

1. Preserve and review this candidate, including the existing Mac-only fixes.
2. Obtain owner authorization before publishing the reconciled plan where
   previously restricted, posting a handoff, merging or installing this change.
3. At the owner's move/reboot timing, verify home boot/login and real reply,
   then perform normal-use soak. Do not force a reboot during ongoing work.
4. Choose an owner-controlled encrypted backup destination before copying
   newer private memory to another medium.
5. Continue Stage 2/3 acceptance using synthetic fixtures; keep Stage 4/5
   authentication and runner installation behind their concrete design gates.

## Final local verification — reconciliation candidate

496 passed, 13 warnings, zero skips in 35.22 seconds on Mac/Python 3.13.16.
The suite ran with an empty inherited environment except explicit runtime
PATH and a disposable LUNA_DB_PATH; Node syntax checks were available.
Compilation, case-safe Git paths and diff whitespace checks passed.
The first full run found one remaining host-port-dependent unit test; its
port probe was isolated and the complete suite then passed. No production
service was stopped or changed. Installed ee067a3 remains clean.

Existing GitHub CI covers #57, not this new local candidate. Preserve the
new commit and obtain exact-head CI after authorized publication.

## Local drafting acceptance — follow-up

The original proposal path failed strict validation twice against public
`luna/skill_catalog.py` in disposable state. The candidate now requests
schema-constrained output only at the local Ollama-compatible endpoint
(port 11434, /v1). Path and base revision are constrained, and the existing
revision, size and Python-syntax validation still apply. Other providers
retain their previous payload, and rejected requests do not trigger a
less-constrained fallback.

The same local qwen2.5-coder:7b then produced a proposal that reached review
on its first attempt in 30.42 seconds. Source remained unchanged, generated
code was not executed, and private memory was not used. This proves one
local drafting scenario, not correctness of the proposed improvement or
a complete test/repair/deployment cycle. The old production failure remains
a preserved historical record; these fixes are not installed yet.

Full regression: 502 passed, 13 warnings, zero skips in 35.91 seconds.
Transport, consent, rejection, retry and local-only scope tests passed.
Reference: https://docs.ollama.com/capabilities/structured-outputs
