# ORBIT · Luna

ORBIT is a local-first, provider-independent AI assistant ecosystem. Luna is its central conversational coordinator. The authoritative build/version is stored in `VERSION`.

## What works now
- Private localhost FastAPI dashboard with persistent SQLite conversations.
- Optional replaceable local/cloud model endpoint configured outside the repository.
- Approval-gated memory suggestions, project notes, technical decisions, and cross-session continuity summaries.
- Automatic local conversation checkpoints for long chats; cross-session use still requires owner approval.
- Local history search with sensitivity filtering.
- Durable allowlisted job queue, goals, backlog, worker restart recovery, and worker heartbeat.
- Read-only readiness doctor, maintenance audit, unified activity timeline, and sanitized Copy safe status support snapshot.
- Validated local SQLite backups plus non-destructive restore planning.
- GitHub Actions regression checks and reviewable sprint/PR workflow.
- Narrow isolated Podman/Docker regression runner for two allowlisted development modules, with immutable local image ID, no network, read-only host mount, unprivileged user, bounded resources, fixed tests, and temporary test grants.
- Two-attempt bounded repair validation. Passing tests means ready for review only.

## What Luna still cannot do automatically
- Apply generated code to the live installation.
- Merge pull requests or deploy production changes.
- Change security policy, credentials, access, networking, or permissions.
- Spend money or start paid provider usage.
- Use arbitrary shell commands/tools selected by a model.
- Expose ORBIT securely to phone/iPad over the internet.
- Access an operational owner-only password vault or private watchdog; those require a separate OS-enforced boundary on the final host.
- Maintain a truly autonomous background ChatGPT ↔ Luna conversation. The current bridge/relay remains bounded and user-mediated.

## Start safely
Use Python 3.11+ (GitHub CI currently tests Python 3.13). From the repository:

```bash
python -m pip install -r requirements.txt
source .venv/bin/activate
bash scripts/verify_and_launch.sh
```

Then open `http://127.0.0.1:8000` on the same machine.

Useful local tools:

```bash
python scripts/luna_doctor.py
python scripts/bootstrap_safe_runner.py
python scripts/watch_luna_activity.py
```

`bootstrap_safe_runner.py` requires Podman or Docker and grants only temporary isolated test authority. It does not enable code application or merging.

## Security
- Keep ORBIT bound to `127.0.0.1`; there is no authenticated remote-access layer yet.
- Never commit API keys, passwords, or owner-vault material.
- Sensitive-input screening is conservative but fallible; do not treat it as a password manager.
- The owner-only vault/watchdog architecture in `SECURITY_BOUNDARIES.md` is a requirement specification, not an operational secure store.
- Backups may contain private conversation data and should be protected accordingly.
- Automatic code application remains disabled even when isolated tests pass.

## Development workflow
Routine development should remain small, reviewable, and test-driven:
1. inspect / plan;
2. prepare bounded change;
3. static validation;
4. isolated tests when eligible;
5. review;
6. explicit application/merge only when separately authorized;
7. verify after installation.

Current project references:
- `docs/ARCHITECTURE.md` — implemented boundaries and future deployment model.
- `docs/RUN.md` — local launch, doctor, runner, activity feed, and security rules.
- `SPRINT_PLAN.md` — current safe-development status and gates.
- `DEVELOPMENT_POLICY.md` — owner-approved development decision boundaries.
- `SECURITY_BOUNDARIES.md` — future vault/watchdog threat model and sensitive intake requirements.
