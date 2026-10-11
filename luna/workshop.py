"""Disposable, non-executing workshop for reviewing bounded Python source drafts.

No shell, subprocess, imports of draft code, dependency installs or live writes.
This is a staging step, NOT a sandbox for running untrusted code.
"""
import ast
import hashlib
import tempfile
from pathlib import Path
from luna.patches import review_patch, ALLOWED_PATHS, MAX_BYTES
from luna.change_guard import prepare_checkpoint

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
    checkpoint=prepare_checkpoint(relative_path,expected_sha256,digest)
    return {"path":relative_path,"base_sha256":expected_sha256,
            "replacement_sha256":digest,"checkpoint":checkpoint,"changed":review["changed"],
            "syntax_valid":True,"bytecode_compiles":True,
            "diff":review["diff"],"staged_in_temporary_workspace":True,
            "workspace_deleted":True,"tests_executed":False,
            "draft_executed":False,"live_files_changed":False,
            "approval_required":True,
            "next_step":"Run trusted tests only in a separately designed restricted runner."}
