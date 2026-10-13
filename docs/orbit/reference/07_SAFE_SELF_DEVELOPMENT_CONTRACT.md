# POJO HELM → THRONE | Section 07: Safe Self-Development and Release

**Status: DESIGN READY / candidate-execution isolation and complete develop→test→repair→review loop NOT IMPLEMENTED OR PROVED ON MAC.** Baseline `560419de5f21102c9c9995de57dd4bb8890837f9`, October 13 2026. Test suite proposed in `07_SELF_DEVELOPMENT_TEST_MATRIX.csv`. Owner permits routine source development with reviewable branches but not unsupervised execution of generated code, host privilege, merge, live apply or release.

## 1. Real capability vs deceptive completion

Current `luna/self_improvement.py` generates predefined proposals; local Ollama model can yield a reviewable constrained draft (one observed scenario in PR #58). Neither is a real self-development cycle. [`luna/restricted_runner.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/restricted_runner.py) explicitly requires Linux `bubblewrap`, CLI owner confirmation, and *is not a Mac sandbox*. [`luna/runner_preflight.py`](https://github.com/jmann358/Orbit-core/blob/560419de5f21102c9c9995de57dd4bb8890837f9/luna/runner_preflight.py) reports inspection only, no kernel proof. A temporary folder/venv is not a security isolation boundary.

The deliverable is one genuinely evidence-driven patch candidate safely tested in a **Mac-supported, adversarially verified isolation environment**, followed by a bounded local repair attempt and independently reviewed draft. A failed test or a proposed patch without verified behavior is never called a completed improvement.

## 2. Exact authority and boundary model

1. **Input:** Luna selects a source-grounded defect/reliability opportunity from Section 02 evidence, with evidence links and an explicit success condition. The source SHA and scope are fixed before proposing code; no automatic feature explosion or arbitrary issue selection from model hallucinations.
2. **Manifest:** Stable proposal ID; exact base Git tree SHA; allowlisted file paths with exact base content hashes; bounded changed bytes; code/test artifacts; task scope and trust tier; tool permissions; model/provider/consent; declared possible side effects; versioned source evidence; expected tests; rollback pointer; expires-at. Mismatch means reject, not rebase invisibly.
3. **Disallowed writes by default:** `AGENTS.md`, security policies, app auth/consent gates, trusted workflows/CI pins, launchers, credentials, `.git`, database/backups, provider billing configuration and release scripts. A future owner-approved scope expansion requires a separate sensitive change ticket and manual review, not developer-model authority.
4. **Sandbox:** host-independent process with actual kernel/VM security boundary on macOS; no mounts of owner home, original working Git tree, SQLite, private backups, cloud credentials, SSH/GitHub tokens, host sockets, keychain or secrets; minimal **read-only** copied allowlisted project files plus ephemeral scratch space; network denied by default. Evaluate a disposable VM or equivalent genuinely isolating executor *after checking supported macOS version and M4 resources*. Do not choose/install a product from HELM alone.
5. **Budget and limits:** bounded wall-clock, CPU, RAM, filesystem, process count, output, log size, number of attempts and parallelism enforced **outside** candidate code. Default one candidate at a time. Resource limit breach kills workload and reports a bounded failure; worker remains healthy. Prevent hidden packages/downloads and billable provider fallback.
6. **Trust:** synthetic/allowlisted trusted tests are baseline; model-generated tests themselves are **untrusted executable code** and only run in the isolated guest. Validate expected tests separately against approved assertions so passing a self-written weak test is not proof. Never execute generated code or dependencies directly on THRONE host.
7. **Repair:** after a failed isolated attempt, use bounded diagnostic output to propose a new revision. No infinite loop. Revalidate all hashes, permissions and cost ceilings. On exhausted budget, mark `attention` with preserved evidence; no silent broadening of allowed file set, tools, attempts or network.
8. **Proof:** Section 02's independent verifier compares exact SHA of tested candidate, attack-suite outcome, base revision, test environment and immutable receipts. Distinguish 'compile passed', 'trusted unit test passed', 'semantic fixture passed', 'isolation attack contained' and 'accepted for review'. No claim of production change from draft completion.
9. **Promotion:** rejected by default. A reviewable patch or draft PR is *not deployment*. Owner specifically approves merge, service update, schema change and release separately. A controlled update requires protected DB backup, migration compatibility check, maintenance window, health check and automatically *bounded* rollback on failed acceptance; no auto-promotion authority from a successful test.
10. **Self-modification oversight:** Luna cannot edit its own audit logs, permission checker, approval evidence or budget reservation to obtain wider authority; immutable or independently auditable records of denied attempts survive. Independent reviewer is an actual different trust boundary or human review, not a second role label pointing to the same unrestricted model.

## 3. Threat and failure cases that must fail closed

- Malicious candidate reads `/Users/...`, SQLite, keychain, environment variables, agent socket, SSH tokens, or hidden `.git` → denied from sandbox.
- Candidate opens network, resolves DNS, contacts localhost/cloud/metadata URLs or a service socket → denied; verify no paid egress.
- Candidate forks/bombs, writes giant files or logs, spawns child processes, sleeps indefinitely, consumes RAM/CPU, or ignores signal → enforced external kill and cleanup without impacting live Luna.
- Candidate uses symlink/hardlink/path traversal, unicode/alternate case path, file-descriptor trick, base hash TOCTOU, or dependency setup escape → rejected or contained. Test on actual target macOS case semantics.
- Candidate falsifies stdout/JSON receipt, replaces tests, asserts its own verification, or manipulates `pytest` exit status → independently re-evaluate trusted proofs; do not label verified.
- Auth grant expires or provider changes mid-queue; changed source tree; stale test; mac restart mid-run → safe `attention`, no replay of billable call or live effect.
- Bad patch breaks service, data schema or policy → prevent promotion or roll back in rehearsal, preserving original DB and valid prior commit.

## 4. THRONE engineering work order

**D07-A (P0, source-only):** Identify/annotate existing draft, manifest, consent, quality gate, worker and runner code. Recover only **behaviorally useful** code from historical PR #1 after feature-level provenance review; no copy/paste of old runner architecture without threat review. Write no privileges during inventory.

**D07-B (P0, owner gate):** Propose one specific macOS security boundary with guest file-mount manifest, implementation dependencies, resource and network restrictions, manual install/rollback and attestation plan. If a safe supported runner cannot be demonstrated, **stop without running untrusted code**.

**D07-C (P0, synthetic):** Connect evidence → manifest → bounded review status and independent receipts, including denial tests, exact SHA, consent expiration, idempotent queue and truncated logs.

**D07-D (P0, approved host):** Exercise hostile candidates on the actual Mac isolation environment using entirely synthetic files/credentials. Test forbidden reads, outbound traffic, escaped processes, resource exhaustion and tampered test reports. Observe host filesystem/network externally; environment's self-report is insufficient.

**D07-E (P1, approved host):** Run one real local model improvement, trusted tests, one bounded repair if needed, external independent verifier and reviewable diff. No live apply. Separately rehearse an approved update/rollback with disposable DB and service; later merge/release needs distinct owner authorization.

## 5. Design closeout

Design cannot grant operational safety by itself. **Product gate:** hostile isolation negative tests, bounded end-to-end loop, independent receipts, backup/rollback rehearsal, consent/budget revocation, reviewer sign-off and owner-accepted limitations, each tied to exact candidate SHA. Sandbox or review failure blocks release and future autonomous application. No code ran on THRONE from HELM.

Mapped gates: T05/T06/T07/T08/T17–T19/T24/T27–T29/T31, V14/V15/V17/V18. Dependencies: 01 scope, 02 proof, 03 privacy, 04 safe rollback, 08 cost. Reopen only if actual threat bypass or new owner trust policy changes the boundary.
