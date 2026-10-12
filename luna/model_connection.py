"""Read-only readiness for Luna's configured model transport.

This is configuration inspection only: no requests, secret values, or provider
model IDs leave the host. Configuration never means an API call has succeeded.
"""
import os
from urllib.parse import urlparse

CLOUD_HOSTS = frozenset({
    "api.groq.com", "api.openai.com", "api.together.xyz",
    "openrouter.ai", "generativelanguage.googleapis.com",
})


def classify_endpoint(endpoint):
    """Classify exactly the endpoints Luna permits for chat history transfer."""
    if not isinstance(endpoint, str) or not endpoint:
        return None
    try:
        parsed = urlparse(endpoint)
        port = parsed.port
    except ValueError:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    if parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1"):
        return "local"
    if (parsed.scheme == "https" and parsed.hostname in CLOUD_HOSTS
            and port in (None, 443)):
        return "cloud"
    return None


def inspect_model_configuration(environ=None):
    """Return safe public flags for the local dashboard. Never contacts a model."""
    env = os.environ if environ is None else environ
    endpoint = (env.get("LUNA_MODEL_URL") or "").rstrip("/")
    model = (env.get("LUNA_MODEL_NAME") or "").strip()
    has_key = bool(env.get("LUNA_API_KEY"))
    kind = classify_endpoint(endpoint) if endpoint else None
    if not endpoint or not model:
        state = "not_configured"
        detail = "Connect a model to enable AI conversation."
    elif kind is None:
        state = "blocked"
        detail = "Model endpoint not permitted. Only loopback or approved HTTPS providers are allowed."
    elif kind == "cloud" and not has_key:
        state = "key_required"
        detail = "Cloud model configured but its API key is missing."
    else:
        state = "configured_unverified"
        detail = "Model settings are present. A successful reply has not been verified."
    return {
        "state": state,
        "detail": detail,
        "transport": kind,
        "model_url_configured": bool(endpoint),
        "model_name_configured": bool(model),
        "model_key_configured": has_key,
        "provider_contacted": False,
        "remote_device_access": False,
    }
