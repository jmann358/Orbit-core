# POJO HELM → THRONE | Section 05: Secure iPhone/iPad Access

**Status: DESIGN READY; actual transport, auth installation, pairing and mobile acceptance pending THRONE and specific owner approval.** Baseline: PR #58 `560419de5f21102c9c9995de57dd4bb8890837f9`, 2026-10-13. Test matrix: `05_MOBILE_SECURITY_TEST_MATRIX.csv`.

## 1. Outcome and current evidence

Use the *same* authoritative Luna on THRONE from the Mac, iPhone and iPad, at home and eventually away from home, without public unauthenticated exposure. Keep the existing web experience, session IDs, goal queue, approvals, receipts and user data rather than running another instance on a phone.

[`luna/device_readiness.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/device_readiness.py) explicitly reports `remote_access_implemented=False` and `safe_to_expose_server=False`; existing local origin/Host checks from ATLAS PR #57 are **not authentication**. The verified Mac service remains bound to `127.0.0.1`. Any local-only proof must not be described as secure mobile access. Privacy provider-context gates in Section 03 precede new remote/cloud flow.

## 2. Threat model and trust boundaries

Threats to test: attacker on shared Wi-Fi or local network, stolen/lost phone, leaked session cookie/token, forged requests from a malicious website, malicious redirects, replay or double-tap approvals, two devices racing an approval, outdated/compromised app, XSS/injection in displayed model or task content, brute-force login, stolen/reused pairing QR, expired or revoked device, stolen backups, MITM/tunnel mistakes and Mac unavailable/offline.

**Trust boundaries:** network transport does not confer app authorization; logged-in chat does not necessarily authorize consequential effects; a model-generated message is untrusted content; device pairing authorizes a narrowly scoped client, not a new memory writer. THRONE owns all server-side decisions.

## 3. Normative architecture contract

1. **Do not expose existing localhost FastAPI to the public Internet.** Default design is owner-confirmed **private authenticated connectivity** ending at THRONE with TLS-encrypted transport. A private overlay/VPN is a candidate, not installed or provider-selected here. The chosen implementation must be verifiably supported on THRONE and both devices. No public port forwarding, disable-firewall shortcuts, or anonymous tunnels.
2. **App authentication is required inside the private transport.** Use an owner-bound credential/passkey-capable or equivalent strong mechanism supported by the chosen stack; never store plaintext reusable credentials, never accept a shared hard-coded password in source or GitHub. Rate-limit and audit authentication and consent-changing operations with redaction.
3. **Pairing:** initiated on the trusted Mac or existing authenticated owner session, short-lived single-use challenge, bound to requesting device and server identity; user confirms device label and permissions. Expired/reused/cross-origin pairing must fail. Record pairs, grants, last used, expiry and revocation without retaining secrets in logs.
4. **Sessions:** secure, expiring credentials; `Secure`, `HttpOnly`, appropriate `SameSite` cookie properties where cookies are used; CSRF tokens or origin protections on every state-changing endpoint; prevent session fixation; credential rotation and explicit logout/revoke. Server checks current revocation on every protected action, including long-running waits and task approvals.
5. **Authorization:** roles/capabilities separated for read chat, create work, approve a specific revision, change model disclosure, manage backups, administer devices. If the UI is mobile, the server must still reject unauthorized requests. High-impact operations require recent owner confirmation/re-auth and exact action/revision/scope, as in Section 01.
6. **Safe rendering:** sanitize assistant-generated text, job outputs, URLs and any markup; no arbitrary script or credential disclosure. Avoid placing access tokens in URLs, screenshots, copyable bug reports, logs or app analytics.
7. **No double execution:** all approvals use atomic server-side compare-and-swap, idempotency keys and expiry. A stale tab/device cannot approve a replaced plan, issue a second command, or override another device's cancellation.
8. **Network transition:** reconnect attempts must distinguish 'not sent', 'sent but response missing', 'queued locally', 'accepted with saved ID' and 'effect verified'. Do not replay uncertain external effects on reconnect. Offline actions are unsubmitted drafts, not authority or evidence of execution; credentials may expire while offline.
9. **Mobile UX:** preserve one conversation/task context and result link, with visible active task plus pending approval. Test phone keyboard, screen readers, touch sizing, loss of signal, rotation, slow responses, sessions/reloads, backgrounding, accessibility/reduced motion. Reject hidden 'approve' buttons or ambiguous completion badges.
10. **Network/privacy controls:** initial pairing and transport changes need explicit owner approval. Each remote model provider/data-class transfer remains separately gated under Section 03. Private mobile access never implies permission for cloud inference or memory replication.

## 4. Implementation and acceptance sequence

**M05-A (P0):** Inventory mutation endpoints (`app.py`, routers, WebSocket/SSE if any) and scope/auth each route including reports, attachments, search and approvals. Add shared authentication/CSRF/revocation middleware with synthetic integration tests. Never turn on the remote listener during development.

**M05-B (P0):** Build device registry and one-time pairing/revocation in a disposable database; ensure paired device cannot become an independent worker or database writer. Ensure credential state survives safe restart.

**M05-C (P0, owner gate):** Propose **one concrete transport** with its exact permissions, costs, supported OS, credential storage, endpoints and rollback before installing it. Default to local-only until approved; don't equate a provider's 'free tier' with an indefinite availability guarantee.

**M05-D (P1):** Implement in-chat state reconciliation (Sections 01–02), accessible phone/tablet rendering, local polling limits, and diagnostics that don't leak secrets.

**M05-E (P0, physical):** Test one real iPhone and iPad on home network and away (if requested), pairing/revocation, lost-device scenario, Mac unavailable, session expiry, concurrent approval races and normal access; capture only sanitized proof.

## 5. Closure and owner boundaries

**Design ready:** all expected behavior and abuse cases specified. **Product accepted only after** exact-head unit/integration tests, real-device tests, security review, approved transport and revocation demonstration. Failed security case blocks any remote exposure. Keep Mac localhost-only on failure.

Owner must approve concrete provider/app install, any Internet-accessible surface, device enrollment, and new private-data transmission scope. No accounts or installations occurred in HELM.

Mapped gates: T10–T15/T22/T23/T26/T30, V01–V03/V10/V18. Dependencies: 01 approval, 02 evidence, 03 provider privacy, 04 recoverability. Reopen only for a concrete security issue, owner scope change, platform requirement or failed acceptance proof.
