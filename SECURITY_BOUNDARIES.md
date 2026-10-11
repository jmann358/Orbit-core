# ORBIT security boundaries — proposed architecture

This document defines requirements, not an implemented or certified security boundary.

## Owner-only vault
- Store vault material outside the ORBIT repository, Luna SQLite databases, prompts, model context, logs, backups, and environment variables.
- On the eventual Mac host, use a separate OS account or independently protected service, with file permissions and encryption keys unavailable to Luna's runtime identity.
- Luna must never have administrator rights, vault decryption keys, credential-provider access, or a generic file-reading tool able to reach vault storage.
- Vault contents must not be mounted into Luna's containers or sent to model providers.
- Owner unlocks and reads the vault through a separately authenticated interface; do not expose vault access through Luna's chat, agent tools, or approval workflow.
- Never claim absolute security: verify filesystem permissions, process isolation, backup scope, key management, and recovery before using it for secrets.

## Independent owner-only watchdog
- Run under an OS identity and storage permissions distinct from Luna's identity.
- Capture only minimal security metadata: timestamp, action type, target category, permission decision, and anomaly reason. Avoid secret values and private message bodies.
- Flag denied file-access attempts, attempted permission escalation, unusual outbound network destinations, security-policy changes, disabled auditing, repeated failures, and unexpected code execution.
- Luna cannot edit, erase, configure, or query the private watchdog logs. Her own ordinary activity log is separate.
- Deliver reports directly to an owner-controlled interface, not via Luna. Limit false positives and retain an owner-controlled purge policy.
- Use append-only remote collection or OS-enforced write-only ingestion when feasible. A local log on the same privileged account is not tamper-proof.
- Watchdog should fail closed on lost telemetry: suspend high-risk autonomy and alert owner.

## Routine autonomy and approvals
- Allow routine planning, read-only diagnostics, approved tests, documentation, and reviewable GitHub draft work.
- Keep owner confirmation for credential access, private data exposure, access expansion, security-policy edits, spending, external publication, destructive changes, and production deployment.
- ChatGPT approval of ordinary GitHub changes is not an authenticated owner approval token.
- No autonomous change may grant Luna access to the vault or watchdog, including indirect access through backup, debug, search, shell, or plugin tools.

## Implementation order
1. Threat model and security policy (this document).
2. Distinct runtime identities and restricted tool broker; deny by default.
3. Owner-only vault with isolated keys and audited restore.
4. Independent watchdog with private storage and owner-only alerts.
5. Adversarial tests for indirect access and log tampering.
6. Only then consider increased autonomous code permissions.
