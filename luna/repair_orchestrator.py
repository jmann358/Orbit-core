"""Bounded repair coordinator for Luna.

A candidate may be validated at most twice. This coordinator never writes live source,
never merges, and never expands permissions.
"""
from luna.patches import review_patch
from luna.repair import RepairState, advance, rollback_plan
from luna.runner_executor import run_fixed

def evaluate_candidate(root, relative_path, expected_sha256, replacement, image_ref,
                       state=None, *, owner_approved=True):
    current=state or RepairState(base_sha256=expected_sha256)
    if current.base_sha256 and current.base_sha256!=expected_sha256:
        raise ValueError("Repair base changed")
    review=review_patch(root,relative_path,expected_sha256,replacement)
    working=RepairState(
        attempts=current.attempts,
        status=current.status,
        base_sha256=expected_sha256,
        candidate_sha256=review["replacement_sha256"],
    )
    evidence=run_fixed(
        root,relative_path,expected_sha256,replacement,image_ref,
        owner_approved=owner_approved)
    if evidence["state"]=="blocked":
        next_state=advance(
            working,tests_passed=False,isolation_verified=False,permission_valid=False)
    else:
        next_state=advance(
            working,tests_passed=evidence["state"]=="passed",
            isolation_verified=True,permission_valid=True)
    return {
        "state":next_state,
        "runner":evidence,
        "retry_allowed":next_state.status=="retry_allowed",
        "ready_for_review":next_state.status=="ready_for_review",
        "needs_attention":next_state.status=="needs_attention",
        "rollback":rollback_plan(next_state),
        "live_files_changed":False,
        "auto_apply":False,
        "merge_allowed":False,
    }
