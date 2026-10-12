"""Read-only, owner-facing summary of what Luna needs next.

An explanation is not an authorization. This module only orders existing
persisted tasks, proposals and statuses; it never calls an AI model, changes
permissions, approves items or runs work.
"""

def _short(value, limit=260):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def summarize(overview, activity, model, missions=(), designs=()):
    """Prioritize visible owner actions without inventing permissions or progress."""
    candidates = []

    def offer(kind, title, explanation, why, action, button, priority, ident=None):
        candidates.append({
            "kind": kind, "id": ident, "title": _short(title, 120),
            "explanation": _short(explanation), "why": _short(why, 400),
            "action": action, "button": button, "priority": priority,
        })

    counts = overview.get("counts", {})
    recent_jobs = activity.get("recent", [])
    failed_jobs = [job for job in recent_jobs if job.get("state") == "attention"]
    queued_jobs = [job for job in recent_jobs if job.get("state") == "queued"]
    working_jobs = [job for job in recent_jobs if job.get("state") == "running"]
    done_jobs = [job for job in recent_jobs if job.get("state") == "completed"]
    active_missions = [mission for mission in missions if mission.get("state") in ("queued", "working")]
    dev_attention = [mission for mission in missions if mission.get("state") == "attention"]
    dev_reviews = [mission for mission in missions if mission.get("state") == "review"]
    pending_designs = [design for design in designs if design.get("status") == "pending"]

    for job in failed_jobs:
        offer("work", "A Luna task needs attention",
              _short(job.get("title") or job.get("kind") or "A task stopped before completion."),
              "This job reported an attention state. Inspect its recorded result before retrying; no retry happens automatically.",
              "activity", "Inspect stopped task", 105, job.get("id"))
    for mission in dev_attention:
        offer("development", "A development task needs attention",
              _short(mission.get("summary") or mission.get("error_code") or "Luna could not finish a draft."),
              "A saved development mission stopped. Agent Studio shows its actual reason and does not install code.",
              "developer", "Inspect development task", 102, mission.get("id"))
    for request in overview.get("requests", ()):
        high = request.get("priority") == "high"
        offer("request", request.get("title") or "Luna has a question",
              request.get("message") or "A saved request is waiting for you.",
              "Luna saved a request for owner input. Reviewing or acknowledging it does not execute code or expand her permissions.",
              "review", "Review Luna's request", 98 if high else 82, request.get("id"))
    for design in pending_designs:
        offer("design", design.get("design", {}).get("title") or "New interface design",
              design.get("direction") or "Luna saved a visual proposal.",
              "This design is only a preview. You can revise, discard or explicitly approve it without running model-written code.",
              "design", "Preview design", 78, design.get("id"))
    for mission in dev_reviews:
        offer("development", "Luna prepared code for review",
              mission.get("summary") or mission.get("path") or "A development draft is ready.",
              "This is a saved, unapplied code proposal. Inspect it in Agent Studio; it is not automatically tested or merged.",
              "developer", "Inspect code proposal", 76, mission.get("id"))
    categories = (
        ("tasks", "task", "A task plan is waiting", "description",
         "Approving a task plan records your decision; it is not permission to run arbitrary commands.", 73),
        ("improvements", "improvement", "An improvement is waiting", "description",
         "Luna's improvement proposal is a plan, not an installed feature.", 71),
        ("drafts", "draft", "A code suggestion is waiting", "summary",
         "Shortlisting or dismissing this draft does not install or execute it.", 69),
        ("notes", "note", "A project note needs review", "content",
         "Only you can decide whether this note becomes approved project context.", 67),
        ("memories", "memory", "A memory suggestion needs review", "content",
         "Personal memory suggestions never become approved automatically.", 65),
    )
    for collection, kind, headline, detail_key, why, priority in categories:
        for item in overview.get(collection, ()):
            offer(kind, item.get("title") or item.get("goal") or headline,
                  item.get(detail_key) or headline, why,
                  "review", "Review and decide", priority, item.get("id"))
    if counts.get("bridge", 0):
        offer("bridge", "ChatGPT bridge messages are waiting",
              str(counts["bridge"]) + " thread(s) need a manual relay or response.",
              "The bridge is user-mediated. Luna cannot silently talk to ChatGPT on your behalf.",
              "bridge", "Open bridge", 63)

    # Model readiness is a truthful configuration inspection, not a provider ping.
    model_state = model.get("state", "not_configured")
    if model_state != "configured_unverified":
        offer("setup", "Connect Luna's AI model",
              model.get("detail") or "Luna needs a working model before she can answer or generate designs.",
              "Her dashboard and saved messages can work without a model, but conversation, generation and autonomous drafting need a valid connection. Model settings are configured on the host.",
              "chat", "Check Luna's connection", 88)
    if not candidates:
        if model_state == "configured_unverified":
            offer("chat", "Talk to Luna",
                  "Her model settings are present. Send a message to verify that she can actually answer.",
                  "Configuration is not proof that the AI provider works. Your conversation stays saved locally.",
                  "chat", "Open conversation", 10)
        else:
            offer("chat", "Start with Luna",
                  "Open her conversation and check the connection status.",
                  "You can use the local dashboard now; model-backed responses require a connected model.",
                  "chat", "Open conversation", 10)
    candidates.sort(key=lambda item: (-item["priority"], item["kind"], item["id"] or 0))
    waiting = [x for x in candidates if x["kind"] != "chat"]
    hidden_bridge_count = max(0, counts.get("bridge", 0) - 1)
    recent = []
    for mission in list(missions)[:8]:
        recent.append({
            "kind": "development", "state": mission.get("state", "unknown"),
            "title": _short(mission.get("summary") or mission.get("path") or "Development task", 120),
            "detail": _short(mission.get("error_code") or "", 140),
            "action": "developer",
            "sort_key": mission.get("updated_at") or mission.get("created_at") or "",
        })
    for job in list(recent_jobs)[:12]:
        recent.append({
            "kind": "job", "state": job.get("state", "unknown"),
            "title": _short(job.get("title") or job.get("kind") or "Local task", 120),
            "detail": _short(job.get("result") or job.get("summary") or "", 140),
            "action": "activity",
            "sort_key": job.get("updated_at") or job.get("created_at") or "",
        })
    recent.sort(key=lambda item: item["sort_key"], reverse=True)
    for item in recent:
        item.pop("sort_key", None)
    return {
        "next": candidates[0],
        "waiting": waiting[:12],
        "more_waiting": max(0, len(waiting) - 12) + hidden_bridge_count,
        "waiting_count": len(waiting) + hidden_bridge_count,
        "work": {
            "queued": max(counts.get("queued_jobs", 0), len(queued_jobs)) + sum(m.get("state") == "queued" for m in active_missions),
            "running": len(working_jobs) + sum(m.get("state") == "working" for m in active_missions),
            "attention": len(failed_jobs) + len(dev_attention),
            "recent": recent[:8],
            "completed_recent": len(done_jobs),
        },
        "model": {"state": model_state, "detail": model.get("detail", ""),
                  "verified": False},
        "read_only": True,
        "approval_required": True,
        "polling_is_not_work": True,
    }
