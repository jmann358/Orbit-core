"""Review-only source patch preparation. No code execution, writes or shell access."""
import ast
import difflib
import hashlib
from pathlib import Path

# Narrow, explicit allowlist. Never edit app entrypoints, policy, secrets or auth.
ALLOWED_PATHS = frozenset({"luna/development.py", "luna/self_improvement.py"})
MAX_BYTES = 30_000

def review_patch(root, relative_path, expected_sha256, replacement):
    if relative_path not in ALLOWED_PATHS:
        raise ValueError("Path is not authorized for draft review")
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64:
        raise ValueError("Expected SHA256 required")
    if not isinstance(replacement,str) or not 1<=len(replacement.encode("utf-8"))<=MAX_BYTES:
        raise ValueError("Replacement exceeds bounded limit")
    base=Path(root).resolve(strict=True)
    target=base/relative_path
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(base):
        raise ValueError("Unsafe or missing target")
    if target.stat().st_size>MAX_BYTES:
        raise ValueError("Original exceeds bounded limit")
    old=target.read_bytes()
    actual=hashlib.sha256(old).hexdigest()
    if actual!=expected_sha256:
        raise ValueError("Base revision mismatch")
    try:
        ast.parse(replacement,filename=relative_path)
    except SyntaxError as exc:
        raise ValueError("Proposed Python source does not parse: "+str(exc)[:180]) from exc
    previous=old.decode("utf-8")
    diff="".join(difflib.unified_diff(previous.splitlines(True),replacement.splitlines(True),
                                   fromfile="a/"+relative_path,tofile="b/"+relative_path))
    return {"path":relative_path,"base_sha256":actual,
            "replacement_sha256":hashlib.sha256(replacement.encode("utf-8")).hexdigest(),
            "diff":diff[:60_000],"changed":previous!=replacement,
            "syntax_valid":True,"tests_run":False,"applied":False,
            "requires_explicit_review":True,
            "note":"A syntax-valid draft is not proven safe. This endpoint never writes files."}
