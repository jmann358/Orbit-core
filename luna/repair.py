"""Deterministic repair workflow state machine. No code execution or file writes."""
from dataclasses import dataclass

MAX_ATTEMPTS=2
TERMINAL=frozenset(("ready_for_review","needs_attention","cancelled"))

@dataclass(frozen=True)
class RepairState:
    attempts: int=0
    status: str="draft"
    base_sha256: str=""
    candidate_sha256: str=""

def advance(state, *, tests_passed, isolation_verified, permission_valid):
    """Accept test evidence only when isolation and approval are independently established."""
    if state.status in TERMINAL:
        raise ValueError("Repair is already terminal")
    if not isolation_verified or not permission_valid:
        return RepairState(state.attempts,"needs_attention",state.base_sha256,state.candidate_sha256)
    if state.attempts>=MAX_ATTEMPTS:
        return RepairState(state.attempts,"needs_attention",state.base_sha256,state.candidate_sha256)
    count=state.attempts+1
    if tests_passed:
        return RepairState(count,"ready_for_review",state.base_sha256,state.candidate_sha256)
    return RepairState(count,"retry_allowed" if count<MAX_ATTEMPTS else "needs_attention",state.base_sha256,state.candidate_sha256)

def rollback_plan(state):
    """Generate instructions only. Never touch source or automatically deploy."""
    return {"action":"restore_verified_base","base_sha256":state.base_sha256,
            "candidate_sha256":state.candidate_sha256,"executed":False,
            "requires_owner_review":True}
