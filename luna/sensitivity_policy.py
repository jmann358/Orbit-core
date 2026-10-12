"""Conservative high-confidence credential/identifier indicators for local chat.

This only classifies obvious text patterns. It is NOT a comprehensive PII
detector, encrypted vault, authorization mechanism or external DLP service.
It never logs, stores or returns matching text.
"""
import re

RULES = (
    ("private_key", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    ("credential_assignment", re.compile(
        r"(?i)\b(?:password|passwd|api[_-]?key|secret[_-]?key|access[_-]?token)"
        r"\s*[:=]\s*\S+")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}")),
    ("social_security_number", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
)


def classify(text):
    if not isinstance(text, str):
        raise TypeError("Chat content must be text")
    if len(text) > 12000:
        raise ValueError("Chat content exceeds screening limit")
    categories = sorted({name for name, rule in RULES if rule.search(text)})
    return {"sensitive": bool(categories), "categories": categories,
            "content_retained": False, "screening_complete": False}
