"""Strict natural-language routing for allowlisted, low-risk jobs only."""
import re

def route_chat_job(message):
    if not isinstance(message, str):
        return None
    text = " ".join(message.lower().strip().split())
    if len(text) > 300 or not text:
        return None
    prefix = r"(?:luna[,!]?\s*)?(?:please\s+)?(?:run|start|queue|perform|do)\s+"
    patterns = (
        (r"(?:a\s+|the\s+)?(?:project\s+|orbit\s+|system\s+)?(?:health\s+check|health\s+scan|health\s+report)", "project_health", "Chat-requested project health check"),
        (r"(?:a\s+|the\s+)?(?:github\s+|ci\s+)(?:status\s+check|checks?\s+review|checks?)", "github_status", "Chat-requested GitHub status check"),
        (r"(?:a\s+|the\s+)?(?:development\s+|scheduler\s+)(?:plan|planning\s+task)", "development_plan", "Chat-requested development plan"),
        (r"(?:your\s+|the\s+)?(?:next\s+)?(?:self-improvement\s+|self improvement\s+)(?:proposal|plan|task)", "self_improvement", "Luna self-improvement proposal"),
    )
    if re.fullmatch(r"(?:luna[,!]?\s*)?(?:please\s+)?(?:draft|prepare|build)\s+(?:the\s+|your\s+)?next\s+(?:roadmap\s+)?improvement[.!]?", text):
        return {"kind":"workshop_draft", "title":"Luna workshop draft"}
    for pattern, kind, title in patterns:
        if re.fullmatch(prefix + pattern + r"[.!]?", text):
            return {"kind":kind, "title":title}
    return None
