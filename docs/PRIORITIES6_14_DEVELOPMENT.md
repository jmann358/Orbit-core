# ORBIT priorities 6–14: safe development milestone

This milestone develops the **local-first foundations** for each remaining
priority. It does **not** claim the nine priorities are complete. Current
GitHub CI runs in a hosted runner, not on the intended always-on Mac mini.

| Priority | Implemented in this milestone | Still needed for completion |
| --- | --- | --- |
| 6. Long-term memory and learning | Source-attributed, user-only, heuristic memory extraction. Preview by session; explicitly queue a candidate; existing owner approval promotes it. No cloud transfer or automatic approval. | More reliable cross-session organization, conflict handling, retention decisions, opt-in summarization and real user trials |
| 7. Multi-agent ecosystem | Read-only specialist handoff envelopes from completed, approved goal steps, with source job IDs and instruction-untrusted labels. | Actual separately sandboxed agents, scoped credentials, runtime permissions, end-to-end supervised agent coordination |
| 8. Mac/iPhone integration | Read-only host readiness report and security prerequisites, specifically denying network readiness. | Real Mac install QA, owner-approved authenticated device pairing, encrypted transport and user-tested mobile interface |
| 9. Provider independence/cost | Record API-reported usage counts for existing Gemini/OpenAI-compatible response paths; show unknown usage and unknown prices accurately. No prompt or key content intentionally recorded. | Configurable provider routing, model capabilities/benchmarks, actual price schedules, proven hard spend enforcement |
| 10. Voice/personality/avatar | Locally persisted owner visual preferences tied to Luna's existing expressive CSS ghost companion. | Voice permission/recording choices, tested synthesis and microphone flow, accessibility, animation improvements |
| 11. Skills and integrations | Explicit static catalog separating existing capabilities from unconnected accounts and describing permission requirements. | Account/provider selection, credential lifecycle, granular scope approvals and tested integrations |
| 12. Proactive assistance | Bounded, on-demand local recommendations based on pending/failed work. Explicit action to save one deduplicated local reminder. | User-approved triggers, notification delivery, attention scheduling and opt-in reliable automation |
| 13. Self-improvement | Read-only gate and evidence checklist that never treats a proposal or passing CI as deployment authority. | Validated improvement measurement, safe reversible changes, bounded experiments and owner-controlled promotion |
| 14. Reliability | Offline consistent SQLite backup, integrity verification, restrictive file permissions, no-overwrite behavior; read-only backup readiness API. | Restore rehearsal, uptime supervision, on-device QA, disaster recovery, host monitoring and secure deployments |

## APIs

- `GET /memory/learning/preview?session={session}` – preview source-linked
  candidate statements from the selected conversation (no persistence).
- `POST /memory/learning/suggest` – request pending review of one
  `{"message_id":123}` from a user message; never auto-approve.
- `GET /memory/learning/sources` – show provenance and review status.
- `GET /agent/goals/{id}/handoff/{position}` – read-only specialist result
  envelope. Not a grant, model prompt or independent runtime.
- `GET /system/device-readiness` – inspect missing security milestones.
- `GET /model/usage` – actual provider-reported token counts, not prices.
- `GET /presentation/settings`, `POST /presentation/settings` –
  persisted visual choices only; no microphone or API activation.
- `GET /skills/catalog`, `GET /skills/plan/{skill_id}` –
  explicit offline integration inventory and required approvals.
- `GET /assist/suggestions`,
  `POST /assist/suggestions/review` – on-demand local review recommendations.
- `GET /development/evidence-gate` – self-improvement review requirements.
- `GET /system/backup-readiness` – status-only, no data exfiltration.

A new **Ecosystem** dashboard tab shows readiness and locally stored
presentation preferences. The **Memory** tab can preview the current session's
review-only candidates. Existing owner review remains authoritative.

## Offline SQLite backup

From a trusted host with the repository available, use this in a Python
interpreter (only on local devices; never paste a DB into ChatGPT/GitHub):

```python
from luna.database_backup import backup_default, verify
report = backup_default()
print(report["verified"], report["sha256"])
# To verify a specific already-created file:
# print(verify("backups/luna-YYYYMMDDTHHMMSSffffffZ.db"))
```

The source database must already exist. The tool creates one new .db
snapshot under `backups/`, verifies SQLite integrity, never overwrites an
existing destination, and never restores or uploads anything. Backups
contain **private conversation records**; treat them as confidential, encrypt
disk backups under the host's native storage protection, and confirm that
the backup directory isn't included in a cloud-sync system.

The existing `scripts/verify_and_launch.sh` does its own simple copy; this
new tool is more strict about SQLite online-consistent snapshots. Switching
the launcher to use it, adding rotation or restoring old databases warrants
a separate review and local validation.

## Safety limitations

- The current API has **no authentication** and must stay bound to
  `127.0.0.1`; no port-forwarding, tunneling, Wi-Fi publication or internet
  exposure. These changes do not create authenticated phone access.
- Memory extraction is intentionally narrow and cannot guarantee detection
  of all sensitive text. Every suggested memory must be reviewed manually
  before promotion. Historical chat text remains data, never privileged
  instructions. Cloud-history opt-ins remain unchanged.
- Provider token metadata can be missing or inconsistent. Such events
  are explicitly **unmetered** rather than free. No verified provider prices
  or billing enforcement are present; it is **not** a spending cap.
- Presentation styles affect the existing CSS display, not a model's
  core identity or voice. Existing chat model calls retain their configured
  provider and prompts.
- Catalog entries are documentation, not connected apps or credentials.
  New integrations, remote access, audio capture and permission changes all
  require separate owner approvals.
- Review-only suggestions cannot run tasks or bypass any permission gate.
  Passing CI is not authorization to merge, deploy or install.

## Future delivery sequence

1. Merge this tested development milestone after explicit owner approval,
   then verify its exact commit on `main`.
2. Test `memory/learning`, `model/usage`, UI and local backup against a
   disposable local database on the intended host.
3. Agree on a security architecture (authentication, pairing, transport,
   revocation, retention), then implement it on an isolated branch only after
   explicit authorization.
4. Establish authenticated, backed-up Mac mini hosting and iPhone access.
5. With approved provider/account access and a real cost meter, introduce
   isolated model agents, skills and optional voice.
6. Exercise recovery and retention scenarios on disposable data before
   declaring any of priorities 6–14 complete.
