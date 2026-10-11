"""Bounded autonomous validator for queued Luna code candidates.

Consumes one durable candidate, runs it only through the isolated validator, and
records safe metadata. Never writes live source or merges.
"""
from pathlib import Path

from luna import development_candidates
from luna.repair import RepairState
from luna.repair_orchestrator import evaluate_candidate

def run_one(root):
    item=development_candidates.claim_next()
    if item is None:
        return {"state":"idle","candidate_id":None}
    previous_attempts=item["attempt_number"]-1
    prior_status="new" if previous_attempts==0 else "retry_allowed"
    repair_state=RepairState(
        attempts=previous_attempts,
        status=prior_status,
        base_sha256=item["base_sha256"],
        candidate_sha256=item["replacement_sha256"],
    )
    try:
        result=evaluate_candidate(
            Path(root),item["path"],item["base_sha256"],item["replacement"],
            state=repair_state,owner_approved=True)
    except Exception as exc:
        safe={"state":"blocked","reason":"validator_exception",
              "tests_executed":False,"live_files_changed":False}
        development_candidates.finish(item["id"],"blocked",safe)
        return {"state":"blocked","candidate_id":item["id"],
                "reason":"validator_exception","exception_type":type(exc).__name__}
    state=result["state"].status
    runner=result["runner"]
    safe_runner={
        "tests_executed":runner.get("tests_executed",False),
        "returncode":runner.get("returncode"),
        "reason":runner.get("reason"),
    }
    development_candidates.finish(item["id"],state,safe_runner)
    return {
        "state":state,
        "candidate_id":item["id"],
        "attempt_number":item["attempt_number"],
        "tests_executed":runner.get("tests_executed",False),
        "live_files_changed":False,
        "auto_apply":False,
        "merge_allowed":False,
    }
