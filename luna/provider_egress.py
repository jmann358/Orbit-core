"""Fail-closed, exact-destination disclosure scopes for Luna's cloud chat.

These environment settings are *not* authentication, owner consent receipts, or
permissions to spend. They are a conservative pre-dispatch protection until
the full versioned, owner-reviewed disclosure UI is implemented.

Each scope must equal "<configured HTTPS model endpoint>|<model name>".
Different providers, endpoints, or models never inherit another scope.
Local loopback inference continues to use Luna's existing local-only rules.
"""

import os
from luna.model_connection import classify_endpoint

SCOPE_ENV = {
    "current_chat": "LUNA_CLOUD_CHAT_SCOPE",
    "personal_memory": "LUNA_CLOUD_MEMORY_SCOPE",
    "project_notes": "LUNA_CLOUD_NOTES_SCOPE",
    "older_excerpts": "LUNA_CLOUD_RECALL_SCOPE",
}


def allowed(endpoint, model, data_class, environ=None):
    """Inspect locally configured scopes without making any network request."""
    if data_class not in SCOPE_ENV:
        raise ValueError("Unknown cloud disclosure data class")
    transport = classify_endpoint(endpoint)
    if transport == "local":
        return True
    if transport != "cloud" or not isinstance(model, str) or not model:
        return False
    env = os.environ if environ is None else environ
    expected = endpoint.rstrip("/") + "|" + model
    return env.get(SCOPE_ENV[data_class]) == expected
