# Patch proposal manifest

`validate_manifest` checks a bounded, allowlisted set of revision hashes and test identifiers.
`manifest_from_reviews` converts successful, changed, unapplied `review_patch` preview reports
into a manifest, rejecting inconsistent status or unauthorized files.

Neither function writes files, executes tests, applies patches, or authorizes deployment.
These functions are not yet wired into the ORBIT API. Owner review is required before
any code installation. Test identifiers are metadata, not shell commands.

Test identifiers are restricted to test file paths under tests/ and are never executed by this module. The path allowlist is imported from luna.patches to prevent policy drift.

`verify_manifest_bases` performs a read-only, symlink-aware SHA-256 check of the current local files before review. This check is not a security sandbox or a deployment authorization.

`proposal_fingerprint` produces a deterministic SHA-256 identifier for proposal metadata. `compare_proposal_fingerprint` detects changes since review. A fingerprint is NOT an approval, signature, or deployment permission.

`verify_replacement_contents` checks that every supplied replacement text matches
its declared SHA-256 digest and that no extra or missing files are present. It
never writes files or grants approval. SHA-256 matching is integrity checking,
not proof that candidate code is safe.

Priority 2 wires the existing manifest validation into `luna.workshop.stage_proposal`
and `POST /development/workshop/proposal`. The review-only API never executes or
installs code. See `docs/PRIORITY2_WORKFLOW.md` for the separately approved,
Linux-only candidate test runner and its environment limitations.
