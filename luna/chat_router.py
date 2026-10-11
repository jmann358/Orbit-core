"""Strict natural-language routing for low-risk jobs only.

Never interpret general conversation or model output as authority to run commands.
"""
import re

def route_chat_job(message):
    if not isinstance(message, str):
        return None
    text = " ".join(message.lower().strip().split())
    if len(text) > 300 or not text:
        return None
    # Explicit requests only; avoid accidental task creation from discussion.
    prefix = r"(?:luna[,!]?\s*)?(?:please\s+)?(?:run|start|queue|perform|do)\s+"
    match = re.fullmatch(prefix + r"(?:a\s+|the\s+)?(?:project\s+|orbit\s+|system\s+)?(?:health\s+check|health\s+scan|health\s+report)[.!]?",text)
    if match:
        return {"kind":"project_health","title":"Chat-requested project health check"}
    match = re.fullmatch(prefix + r"(?:a\s+|the\s+)?(?:github\s+|ci\s+)(?:status\s+check|checks?\s+review|checks?)[.!]?",text)
    if match:
        return {"kind":"github_status","title":"Chat-requested GitHub status check"}
    match = re.fullmatch(prefix + r"(?:a\s+|the\s+)?(?:development\s+|scheduler\s+)(?:plan|planning\s+task)[.!]?",text)
    if match:
        return {"kind":"development_plan","title":"Chat-requested development plan"}
    return None
