"""Disposable, non-executing workshop for reviewing bounded Python source drafts.

No shell, subprocess, imports of draft code, dependency installs or live writes.
This is a staging step, NOT a sandbox for running untrusted code.
"""
import ast
import hashlib
import tempfile
from pathlib import Path
from luna.patches import review_patch, ALLOWED_PATHS, MAX_BYTES

def stage(root, relative_path, expected_sha256, replacement):
    """Validate a revision-locked draft in an automatically deleted temp directory."""
    review=review_patch(root,relative_path,expected_sha256,replacement)
    with tempfile.TemporaryDirectory(prefix="orbit-workshop-") as directory:
        work=Path(directory)
        target=work/relative_path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(replacement,encoding="utf-8")
        parsed=ast.parse(target.read_text(encoding="utf-8"),filename=relative_path)
        # This compiles bytecode but does NOT execute it.
        compile(parsed,relative_path,"exec")
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if digest!=review["replacement_sha256"]:
            raise ValueError("Staged content digest mismatch")
    return {"path":relative_path,"base_sha256":expected_sha256,
            "replacement_sha256":digest,"changed":review["changed"],
            "syntax_valid":True,"bytecode_compiles":True,
            "diff":review["diff"],"staged_in_temporary_workspace":True,
            "workspace_deleted":True,"tests_executed":False,
            "draft_executed":False,"live_files_changed":False,
            "approval_required":True,
            "next_step":"Run trusted tests only in a separately designed restricted runner."}


def stage_proposal(root, changes, tests=None):
    """Bind staged, syntax-checked source to an integrity-checked review manifest.

    This is preparation ONLY: it neither executes tests nor changes project files.
    A fingerprint identifies content; it is never an approval credential.
    """
    from luna.patch_manifest import (
        MAX_FILES, manifest_from_reviews, proposal_fingerprint,
        verify_manifest_bases, verify_replacement_contents,
    )

    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_FILES:
        raise ValueError("Expected between 1 and 5 changes")
    if any(not isinstance(c, dict) or set(c) !=
           {"path", "base_sha256", "replacement"} for c in changes):
        raise ValueError("Each change requires path, base_sha256 and replacement")
    paths = [c["path"] for c in changes]
    if any(not isinstance(path, str) for path in paths) or len(set(paths)) != len(paths):
        raise ValueError("Duplicate or invalid change paths")

    reports = []
    replacements = {}
    for change in changes:
        report = stage(root, change["path"], change["base_sha256"],
                       change["replacement"])
        reports.append({
            "path": report["path"],
            "base_sha256": report["base_sha256"],
            "replacement_sha256": report["replacement_sha256"],
            "changed": report["changed"],
            "syntax_valid": report["syntax_valid"],
            "applied": False,
            "tests_run": False,
            "requires_explicit_review": True,
        })
        replacements[change["path"]] = change["replacement"]

    manifest = manifest_from_reviews(reports, tests)
    verify_manifest_bases(root, manifest)
    verify_replacement_contents(manifest, replacements)
    return {
        "manifest": manifest,
        "fingerprint": proposal_fingerprint(manifest),
        "diffs": [{"path": report["path"], "diff": report["diff"]}
                  for report in _reviews_with_diffs(root, changes)],
        "syntax_valid": True,
        "base_revisions_verified": True,
        "replacement_contents_verified": True,
        "workspace_deleted": True,
        "applied": False,
        "tests_run": False,
        "requires_explicit_review": True,
    }


def _reviews_with_diffs(root, changes):
    """Compute bounded diff previews; source is never written."""
    return [review_patch(root, c["path"], c["base_sha256"], c["replacement"])
            for c in changes]
