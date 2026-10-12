"""Real chat-to-work receipts for ORBIT's existing supervised workers.

No model-generated text becomes an executable command. All jobs are
deterministic, allowlisted, auditable and review-only where appropriate.
"""
import os
import re

from luna import core, jobs, self_build, developer_agent
from luna.developer_model import configuration

_AFFIRMATIVE = re.compile(
    r"(?:yes|yeah|yep|sure|okay|ok)(?:[,! .]*(?:let'?s do it|go ahead|do it|start|please))?[.! ]*\Z",
    re.I,
)
_PROGRESS = re.compile(
    r"(?:luna[,! ]*)?(?:please )?(?:"
    r"(?:what(?:'s| is) (?:the )?(?:status|progress)(?: of (?:your )?(?:self-improvement|development|improvements))?)|"
    r"(?:how (?:is|are) (?:your )?(?:self-improvement|development|improvements|self-building)(?: going)?)|"
    r"(?:show|check|report) (?:your )?(?:development|self-improvement|self-building) (?:progress|status)|"
    r"(?:what have you (?:actually )?(?:done|built|improved))|"
    r"(?:are you (?:actually )?(?:working|improving yourself))"
    r")[?.! ]*\Z", re.I,
)
_WORK_PROMISE = re.compile(
    r"\b(?:health[\s-]?check|diagnostic|self[\s-]?improv|self[\s-]?build|"
    r"development|memory[\s-]?approval|draft|code|project health)\b", re.I,
)


def _developer_state():
    """Facts from durable records and flags, never a claim of live inference."""
    state = developer_agent.status(core.DB_PATH)
    missions = developer_agent.list_missions(core.DB_PATH)
    model = configuration()
    worker_flag = os.environ.get("LUNA_WORKER_ENABLED") == "1"
    return state, missions, model, worker_flag


def _mission_line(record):
    if not record:
        return "No saved development mission exists."
    label = "Mission #" + str(record["id"]) + " (" + record["path"] + ")"
    status = record["state"]
    if status == "review":
        return label + ": a validated, unapplied code draft is ready for your review."
    if status == "attention":
        return label + ": stopped and needs review; no automatic retry."
    if status == "working":
        return label + ": marked working; this doesn't prove the model responded."
    if status == "queued":
        return label + ": queued, not yet drafted."
    return label + ": recorded state is " + str(status) + "."


def _blockers(state, model, worker_flag):
    blockers = []
    if state["paused"]:
        blockers.append("the development agent is paused")
    if not model["ready"]:
        if model["transport"] == "cloud":
            blockers.append("cloud development-model permission is not enabled")
        else:
            blockers.append("the separate development model is not enabled or configured")
    if not worker_flag:
        blockers.append("the background development-worker setting is off")
    if state["daily_model_attempts"] >= state["daily_model_attempt_limit"]:
        blockers.append("today's development-model attempt limit has been reached")
    return blockers


def progress_message():
    state, missions, model, worker_flag = _developer_state()
    latest = missions[0] if missions else None
    blockers = _blockers(state, model, worker_flag)
    output = _mission_line(latest)
    if blockers:
        output += "\nBlocked: " + "; ".join(blockers) + "."
    elif latest and latest["state"] == "queued":
        output += "\nModel and worker settings are present, but no successful draft has been verified."
    if missions:
        output += "\nSee Agent Studio for the saved mission and evidence: /agent/studio."
    return output


def start_improving():
    """Queue diagnostics and one real review-only development mission."""
    diagnostics = None
    mission = None
    health_error = None
    mission_error = None
    try:
        diagnostics = jobs.queue_once(
            "project_health", "Inspect ORBIT before Luna's next improvement")
    except ValueError:
        health_error = "the health-check queue is unavailable"
    try:
        mission = self_build.start(core.DB_PATH)
    except ValueError as exc:
        mission_error = str(exc)
    if diagnostics is None and mission is None:
        return {"kind": "notice", "reply":
                "I couldn't save new work. " +
                (mission_error or "The supervised task queue is unavailable.") +
                " Check Agent Studio and the task inbox; I didn't change source files."}
    lines = []
    if diagnostics is not None:
        lines.append(
            "I " + ("queued" if diagnostics["created"] else "reused") +
            " the actual project-health task #" + str(diagnostics["id"]) +
            ". The local worker still needs to run it; I haven't claimed a pass.")
    elif health_error:
        lines.append("Local diagnostic wasn't queued (" + health_error + ").")
    if mission is not None:
        lines.append(
            "I " + ("queued" if mission["created"] else "reused") +
            " development mission #" + str(mission["mission_id"]) +
            " for " + mission["path"] + ". The result will be a review-only code draft, not an installed change.")
    elif mission_error:
        lines.append("No development draft queued: " + mission_error + ".")
    state, _, model, worker_flag = _developer_state()
    blockers = _blockers(state, model, worker_flag)
    if mission is not None:
        if blockers:
            lines.append("Development is BLOCKED until " + "; ".join(blockers) + ".")
            lines.append("A conversational AI connection does not automatically authorize software-development model calls.")
        else:
            lines.append("Development model and worker settings are enabled; inference has not been verified.")
    lines.append(
        "Check real results in Agent Studio (/agent/studio) and Luna's Work panel. "
        "I won't ask you to paste scripts or recreate the existing SQLite memory system.")
    result = {"kind": "queued_task", "reply": "\n".join(lines)}
    if mission is not None:
        result["mission_id"] = mission["mission_id"]
    if diagnostics is not None:
        result["job_id"] = diagnostics["id"]
    return result


def parse(message, session=None):
    """Only direct user intent routes to real work; never model output."""
    if not isinstance(message, str) or len(message) > 300:
        return None
    if self_build.is_start_command(message):
        return "start"
    normalized = " ".join(message.strip().split())
    if _PROGRESS.fullmatch(normalized):
        return "progress"
    if _AFFIRMATIVE.fullmatch(normalized):
        # An affirmative cannot approve an action invented by the model.
        # A recent confirmed work receipt only triggers read-only progress.
        previous = core.history(session, 4) if session else []
        if len(previous) >= 2 and previous[-1]["role"] == "user":
            prior = previous[-2]
            if prior["role"] == "assistant" and (
                prior["content"].startswith("I queued the actual project-health task #") or
                prior["content"].startswith("I reused the actual project-health task #")
            ):
                return "progress"
            if prior["role"] == "assistant" and _WORK_PROMISE.search(prior["content"]):
                return "unverified_yes"
    return None


def handle(action):
    if action == "start":
        return start_improving()
    if action == "progress":
        return {"kind": "work_status", "reply": progress_message()}
    if action == "unverified_yes":
        return {
            "kind": "work_status",
            "reply": (
                "My previous suggestion was conversational text, not a saved ORBIT task. "
                "Your 'yes' didn't secretly authorize or run anything. "
                "To start real diagnostics and a bounded code draft, say "
                "'Luna, begin improving yourself.' The actual status will then "
                "appear on my home screen."
            ),
        }
    return None
