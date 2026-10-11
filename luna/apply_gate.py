"""Fail-closed gate for future Luna code application.

This module decides readiness only. It never writes files or merges code.
"""
from luna.patches import ALLOWED_PATHS

def evaluate(relative_path, repair_state, checkpoint, *, isolation_enabled, apply_permission):
    checks={
        "path_allowed":relative_path in ALLOWED_PATHS,
        "repair_ready":getattr(repair_state,"status",None)=="ready_for_review",
        "checkpoint_matches":isinstance(checkpoint,dict) and checkpoint.get("path")==relative_path,
        "verified_base_required":isinstance(checkpoint,dict) and checkpoint.get("requires_verified_base") is True,
        "isolation_enabled":isolation_enabled is True,
        "apply_permission":apply_permission is True,
    }
    return {
        "ready":all(checks.values()),
        "checks":checks,
        "writes_performed":False,
        "merge_performed":False,
        "rollback_required":True,
        "owner_review_required":True,
    }
