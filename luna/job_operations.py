"""One supervised step of the existing allowlisted local task worker.

No extra agent loop, shell access, provider calls, repository writes or
privilege escalation. Executes only the processor supplied by app.py.
"""
import sqlite3

from luna import core, jobs


def run_once(processor, now=None):
    """Claim, execute, audit, and bound retries for a single trusted task."""
    if not callable(processor):
        raise ValueError("A trusted task processor is required")
    job = jobs.claim_next(now=now)
    if job is None:
        return None
    try:
        success, summary = processor(job)
        if type(success) is not bool:
            raise ValueError("Invalid trusted task outcome")
        summary = str(summary)[:1500]
    except Exception:
        success, summary = False, "Task failed; inspect the server logs"
    retryable = (
        not success and job["kind"] == "github_status"
        and summary == "GitHub unavailable"
    )
    completed = jobs.finish_job(
        job["id"], success, summary, retryable=retryable, now=now
    )
    if not completed:
        # An invalid transition must never initiate a second execution.
        return {"id": job["id"], "state": "attention",
                "error": "Unable to persist job outcome; investigate"}
    result = jobs.get_job(job["id"])
    state = result["state"]
    # The local health observer re-reads fixed source files independently.
    # A missing/stale/invalid result stays unverified, never becomes a false pass.
    if state == "completed" and job["kind"] == "project_health":
        try:
            from luna.result_verification import verify_local_health
            verify_local_health(job["id"])
        except (ValueError, OSError, sqlite3.Error):
            # Observation is an optional separate evidence operation; the
            # durable worker result remains available with no verified badge.
            pass
    core.record_agent_run(
        "job:" + str(job["id"]),
        "passed" if state == "completed" else
        "retry_wait" if state == "retry_wait" else "attention",
        summary,
    )
    if retryable and state == "attention":
        # One deduplicated, locally stored escalation; nothing is sent out.
        from luna.requests import create_request
        create_request(
            "issue", "medium", "GitHub check retry limit reached",
            "The read-only GitHub status check failed after bounded retries. "
            "Please inspect the connection or CI status. No permissions or "
            "code were changed.",
            "Job #" + str(job["id"]) + "; " + summary[:250],
        )
    return result
