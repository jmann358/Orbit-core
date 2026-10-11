"""Conservative sensitivity screening for intake routing.

This module never stores input, logs content, or grants access to a vault.
It is NOT a secure intake broker; screening must eventually run before Luna.
"""
import re

RULES = (
    ("private_key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("credential_assignment", re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*\S+")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}")),
    ("social_security_number", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
)
def classify(text):
    """Return labels only, never excerpts or matched secret values."""
    if not isinstance(text,str):
        raise TypeError("Input must be text")
    if len(text)>100_000:
        raise ValueError("Input exceeds screening limit")
    categories=sorted({name for name,pattern in RULES if pattern.search(text)})
    return {"sensitive":bool(categories),"categories":categories,
            "recommended_action":"quarantine" if categories else "review_if_uncertain",
            "content_retained":False,"vault_write_performed":False}
