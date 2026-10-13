"""Stable read-only result receipts from existing durable ORBIT records.

Do not create new parallel task storage. A receipt is a projection of the
authoritative work item, its recorded events, or an existing goal/report.
A 'completed' database state is a worker-reported outcome, not independent
proof of real-world execution or model correctness.
"""
from luna import goals, jobs


def job_receipt(job_id):
    if type(job_id) is not int or job_id < 1:
        return None
    record = jobs.get_job(job_id)
    if record is None:
        return None
    events = jobs.list_events(job_id)
    state = record["state"]
    receipt = {
        "receipt_id": "job:" + str(job_id),
        "kind": "job",
        "id": job_id,
        "title": record["title"],
        "job_kind": record["kind"],
        "goal_id": record["goal_id"], "goal_revision": record["goal_revision"],
        "goal_plan_digest": record["goal_plan_digest"],
        "state": state,
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "attempt_count": record["attempt_count"],
        "max_attempts": record["max_attempts"],
        "recorded_result": record["result"] if state in (
            "completed", "attention", "cancelled"
        ) else "",
        "worker_reported_complete": state == "completed",
        "independently_verified": False,
        "events": events,
        "result_url": "/agent/jobs/" + str(job_id) + "/receipt",
        "read_only": True,
    }
    from luna.result_verification import verification_for_job
    receipt.update(verification_for_job(record))
    return receipt


def goal_receipt(goal_id):
    if type(goal_id) is not int or goal_id < 1:
        return None
    report = goals.goal_report(goal_id)
    if report is None:
        return None
    steps = []
    for step in report["steps"]:
        job = step["job"]
        steps.append({
            "position": step["position"],
            "kind": step["kind"],
            "label": step["label"],
            "state": step["state"],
            "job_id": step["job_id"],
            "job_state": job["state"] if job else None,
            "recorded_result": job["result"] if job and job["state"] in (
                "completed", "attention", "cancelled") else "",
            "result_url": "/agent/jobs/" + str(step["job_id"]) + "/receipt"
                if job else None,
        })
    consistent_complete = (report["state"] == "completed"
                           and bool(steps)
                           and all(step["state"] == "completed"
                                   and step["job_state"] == "completed"
                                   for step in steps))
    return {
        "receipt_id": "goal:" + str(goal_id),
        "kind": "goal",
        "id": goal_id,
        "objective": report["objective"],
        "revision": report["revision"], "plan_digest": report["plan_digest"],
        "approval_digest": report["approval_digest"],
        "approval_event_id": report["approval_event_id"],
        "created_at": report["created_at"], "updated_at": report["updated_at"],
        "predecessor_id": report["predecessor_id"], "successor_id": report["successor_id"],
        "in_flight": report["in_flight"], "outcome_uncertain": report["outcome_uncertain"],
        "state": report["state"],
        "completed_steps": report["completed_steps"],
        "total_steps": report["total_steps"],
        "blocked_reason": report["blocked_reason"],
        "steps": steps,
        "events": report["events"],
        "worker_reported_complete": consistent_complete,
        "independently_verified": False,
        "inconsistent_completion_state": report["state"] == "completed"
            and not consistent_complete,
        "result_url": "/agent/goals/" + str(goal_id) + "/receipt",
        "read_only": True,
    }
