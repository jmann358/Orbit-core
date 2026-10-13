# POJO HELM — Authoritative Offline Design Closure Register

**Updated 2026-10-13.** Full Section 01–08 designs and associated acceptance matrices are available in this package. **DESIGN READY is not implementation, a passed test or an owner-approved release.** This register is the canonical status for HELM output only. Re-fetch latest issue [#52](https://github.com/jmann358/Orbit-core/issues/52), PR [#58](https://github.com/jmann358/Orbit-core/pull/58) and the actual THRONE installed SHA before doing live work.

| Section | Contract | Planned acceptance scenarios | HELM design | THRONE implementation/real proof |
|---|---|---:|---|---|
| 01 Mission plan / approvals / lifecycle | `01_MISSION_APPROVAL_LIFECYCLE_CONTRACT.md` | 28 | **DESIGN READY** | PENDING |
| 02 Independent result verification | `02_RESULT_EVIDENCE_VERIFICATION_CONTRACT.md` | 44 | **DESIGN READY** | PENDING |
| 03 Memory/privacy/retention | `03_PRIVACY_MEMORY_RETENTION_CONTRACT.md` | 72 | **DESIGN READY** | PENDING |
| 04 Backup/uptime/disaster recovery | `04_BACKUP_UPTIME_RECOVERY_CONTRACT.md` | 29 | **DESIGN READY** | PENDING, includes physical-host proof |
| 05 Authenticated iPhone/iPad | `05_SECURE_MOBILE_ACCESS_CONTRACT.md` | 31 | **DESIGN READY** | PENDING, network consent + real devices |
| 06 Restricted cloud blackout companion | `06_CLOUD_BLACKOUT_COMPANION_CONTRACT.md` | 27 | **DESIGN READY** | PENDING, free provider decision + owner consent |
| 07 Mac-isolated self-development | `07_SAFE_SELF_DEVELOPMENT_CONTRACT.md` | 31 | **DESIGN READY** | PENDING, sandbox approval + adversarial test |
| 08 Budget/specialists/financial pilot + future experience | `08_RESOURCE_FINANCIAL_SPECIALISTS_CONTRACT.md` | 31 | **DESIGN READY** | PENDING, funding/account grants and later optional track |
| **Total** | **Eight contracts** | **293 proposed scenarios** | **8 of 8 specified** | **No new Section 04–08 cases run against Luna** |

All prior Section 01–03 scenarios are also **planned acceptance**, not proven merely because their specification exists. The separate older synthetic evidence assessor passed 15 offline fixture tests; it is not integration proof. No additional model/host tests were run in HELM.

## Product baseline and evidence hierarchy

- Published: `main` remains labeled `pojo.2` at `baf96abff8105b89e7b4c924ff03921f084923b5` at prior checkpoint.
- Latest inspected cumulative source: open, draft PR #58, exact head `560419de5f21102c9c9995de57dd4bb8890837f9`.
- Last Mac record in issue #52: that candidate installed, actual local model reply, health job and controlled service restart persistence; GitHub + Mac suites reported 502 passed / 13 warnings. **HELM cannot verify the Mac live during transport.**
- Mac full home boot/login, independent encrypted later-state backup, sustained soak, authenticated remote phone, cloud standby, safe Mac generated-code runner and full autonomous develop/test/repair loop remain unverified.
- Superseding owner direction: **THRONE primary, one authoritative memory writer, and a *required but future-approved* free cloud blackout companion**. Prior sole-host/no-standby document text is historical and should be reconciled when THRONE next edits documents.

## Exact remaining decision boundaries (not invitations to re-ask settled questions)

1. Owner chooses and authorizes encrypted **independent backup target** for newer THRONE data. No backup file is copied from HELM.
2. Owner schedules **physical reboot/transport/soak** after THRONE is stationary. FileVault owner login remains required.
3. Owner authorizes one **specific secure transport/auth provider and device enrollment** after implementation plan and supported-platform review. No public-facing port now.
4. Owner approves any **cloud account**, specific provider's verified $0 plan, minimum disclosure packet, retention and deletion limits. Failure to find truly bounded free service is a reportable provider-selection block, not consent to spend.
5. Owner authorizes Mac-supported **isolated runner installation**, and later exact generated-code execution/merge/release separately. PR #1 legacy code is untrusted until reviewed.
6. Owner chooses concrete **connector**, notification channel and **first financial pilot** only after reviewable candidates and separate spend/outreach authority; voice/audio provider consent likewise future.

## Frozen decisions / safety

- $0 discretionary spending; no hidden cloud paid retry, financial transaction or customer outreach.
- One THRONE writer. Cloud standby is not a second writer or an automatic database takeover.
- Preserve personal memories, chats and backups under Retention C until owner-approved deletion. Personal memory approval and private context scopes apply across all new features.
- Approval is revision/action/provider bound; proposed work is not automatically runnable. Independent proof separate from worker completion.
- GitHub and live THRONE were unchanged by HELM's specification work. Merge/release/install require distinct authority.

## Procedure for THRONE

Read `THRONE_START_HERE_2026-10-13.md`, current GitHub and installed state, then implement one **bounded P0 package at a time**, comparing with existing tests so cases aren't duplicated. Use a single evidence ledger: `planned` → `implemented in branch` → `synthetic passed` → `Mac/device/provider passed` → `owner accepted` → `published`. No generic audits or repeated preference questionnaires. Reopen a contract only for demonstrable contradiction, new vulnerability, failed acceptance test or changed owner requirement. Never treat this lock as a guarantee there are no undiscovered defects.
