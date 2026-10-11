"""Fail-closed checkpoint metadata for reviewable Luna code drafts.

Stores only path and digests. It does not copy source, modify files, or restore code.
"""
import hashlib
import re
from luna.patches import ALLOWED_PATHS

_SHA256=re.compile(r"^[0-9a-f]{64}$")

def prepare_checkpoint(relative_path, base_sha256, replacement_sha256):
    if relative_path not in ALLOWED_PATHS:
        raise ValueError("Checkpoint path is not authorized")
    if not isinstance(base_sha256,str) or not _SHA256.fullmatch(base_sha256):
        raise ValueError("Invalid base digest")
    if not isinstance(replacement_sha256,str) or not _SHA256.fullmatch(replacement_sha256):
        raise ValueError("Invalid replacement digest")
    token=hashlib.sha256(
        (relative_path+"\n"+base_sha256+"\n"+replacement_sha256).encode("utf-8")
    ).hexdigest()
    return {
        "checkpoint_id":token,
        "path":relative_path,
        "base_sha256":base_sha256,
        "replacement_sha256":replacement_sha256,
        "source_retained":False,
        "automatic_restore":False,
        "requires_verified_base":True,
        "requires_review":True,
    }
