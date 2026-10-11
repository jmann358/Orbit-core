# Priority 2 — bounded proposal preparation and controlled candidate testing

## What is connected

`POST /development/workshop/proposal` takes 1–5 full-file Python changes. Each
entry has exactly `path`, `base_sha256`, and `replacement`; `tests` is an optional
array of up to ten test paths. The endpoint:

1. Checks the existing revision hash and the shared `luna.patches.ALLOWED_PATHS`.
2. Parses and compiles candidate code without importing or executing it.
3. Stages drafts in deleted temporary directories, never overwriting live source.
4. Builds a `luna.patch_manifest` with exact content digests and selected test IDs.
5. Verifies base and replacement hashes, and returns diffs and a canonical fingerprint.

Returned status is always `applied: false`, `tests_run: false`, and
`requires_explicit_review: true`. The fingerprint identifies review content,
NOT authorization. This API never executes or applies any candidate.

`GET /development/runner/preflight` reports whether the `bwrap` program can
be located. It does NOT establish that the Linux kernel permits namespaces.

### API example

```json
{
  "changes": [
    {
      "path": "luna/development.py",
      "base_sha256": "<exact lowercase SHA-256 of current source>",
      "replacement": "<complete revised Python source text>"
    }
  ],
  "tests": ["tests/test_development_engine.py"]
}
```

Only `luna/development.py` and `luna/self_improvement.py` are currently
allowlisted for candidate changes. `tests` paths must match manifest rules;
the runner separately requires those files to actually exist in the trusted
source tree. No user-provided shell commands or test selectors are accepted.

## Manual restricted test runner

`luna/restricted_runner.py` is a **local CLI only**. It cannot be started
through the web API, scheduler, GitHub shared tasks, or an autonomous agent.

The owner must review the manifest, diffs and full SHA-256 fingerprint.
Prepare a local `candidate.json` document containing exactly two keys:

```json
{
  "manifest": {
    "files": [{
      "path": "luna/development.py",
      "base_sha256": "<original digest>",
      "replacement_sha256": "<candidate digest>"
    }],
    "tests": ["tests/test_development_engine.py"]
  },
  "replacements": {"luna/development.py": "<complete candidate source>"}
}
```

The `manifest` is the `manifest` returned from the preview API; the
`replacements` are the precise code text originally submitted, not the diff.

From the repo root, after reviewing the full fingerprint:

```bash
python -m luna.restricted_runner candidate.json
```

The CLI prints the expected fingerprint and asks the owner to **type it in
full**, for one test run only. No response or wrong response means no tests.

Requires Linux, a *preinstalled* system `bubblewrap` executable, and
kernel support for unprivileged user namespaces. The runner never installs
packages, adds permissions, or degrades to unsandboxed execution when a
prerequisite fails.

The intended sandbox uses `--unshare-all` (including network namespace),
a namespace-mapped UID/GID (no elevated host identity), a read-only allowlisted source snapshot and host system
libraries, a private writable `/tmp`, cleared environment variables, a
30-second timeout, limits on virtual memory and test output. It executes
only listed pre-existing trusted test paths. It makes no modifications to
live source and deletes its candidate snapshot afterwards.

**Limits:** OS sandboxing is defense in depth, not a guarantee against
kernel or sandbox vulnerabilities. A usable Python environment and
namespaces are platform-specific. Kernel isolation has not been exercised
on the Chromebook or Mac. The Mac is not Linux and requires a separately
designed runner (or a Linux VM) before candidates can be run there.

The existing `/project/test-baseline` endpoint runs trusted repository tests
in a **temporary directory, not an OS sandbox**. Never send model-generated
code to that endpoint or present it as candidate-test isolation. GitHub
Actions continues to check trusted PR revisions independently.

## Permission boundaries

- No autonomous test runs, source application, PR publishing or merge.
- Local full-fingerprint review is required for every candidate execution.
- No repo credentials or personal/home files are mounted into the sandbox.
- No dependency installation or network access is permitted by this workflow.
- Owner approval is still required for enabling network/device access,
  dependency installation, code application, deployment, and sensitive changes.
- If bubblewrap or kernel isolation fails, record the blocker and do not
  silently execute Python on the host.

## Verification

Regression tests cover manifest binding, fingerprint stability, stale
source revisions, duplicate/unallowlisted paths, candidate tampering,
missing tests, missing bubblewrap, timeout reporting, read-only host
snapshots, and sandbox command arguments. The GitHub PR CI suite checks
Python syntax and the complete trusted repository tests.

**Not yet delivered:** unattended safe code modification, automatic test
repair/revert loop, executable Mac sandbox, or auto-merged PRs. Those are
separate owner-approved capabilities, not implied by Priority 2.
