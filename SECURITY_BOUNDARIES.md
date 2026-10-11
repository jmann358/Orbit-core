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

## Sensitive-information intake and quarantine (owner requirement)
The vault is both an owner-only credential manager and a review destination for
potentially sensitive material encountered during authorized Luna work.

- Intake and classification must run in a separate trusted broker **before**
  content reaches Luna's model context whenever technically possible.
- Classifications include credentials, authentication tokens, personal identifiers,
  financial/medical records, private documents, and owner-defined custom rules.
- Default for uncertain matches: quarantine, not discard or automatically publish.
- Quarantined payloads are encrypted for the owner and are never returned to Luna.
  Luna receives only an opaque receipt and a minimal generic handling status.
- Owner-only review actions: preserve in vault, permanently delete according to a
  defined retention policy, release a sanitized version, or create/update a future
  classification rule. Rule edits require owner authentication.
- Never store raw secret payloads, previews, excerpts, or credential fingerprints in
  Luna's database, GitHub, standard logs, model prompts, telemetry, or watchdog reports.
- For passwords, use a vetted password-manager/cryptographic storage design rather
  than implementing custom encryption. The owner-only interface must enforce
  authentication, lockout/rate limits, and secure recovery.
- Vault key management must be separate from Luna and the intake worker. The intake
  service may encrypt using a public key without receiving decryption capability.
- Classification is fallible. Provide a private review queue, expiration/retention
  controls, and a clear distinction between deletion from the vault and copies
  previously disclosed to models or third-party services.
- The private watchdog records only intake events and policy outcomes, not payloads.
- **Not implemented yet.** Do not use this repository as a password manager or
  deposit real secrets until independent storage and isolation are verified.
