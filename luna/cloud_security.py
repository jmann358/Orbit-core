"""Portable, fail-closed owner access gate for a future cloud-hosted Luna.

NOT activated by default. It protects HTTP and WebSocket requests only when
LUNA_CLOUD_MODE=1 and an owner secret is supplied out of band. Never put a
secret in a URL, GitHub, browser localStorage, or an image.
"""
import hmac
import os
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

LOOPBACK = frozenset(("127.0.0.1", "::1", "localhost"))
SAFE_METHODS = frozenset(("GET", "HEAD", "OPTIONS"))
MIN_SECRET_LENGTH = 32


def cloud_mode(environ=None):
    env = os.environ if environ is None else environ
    return env.get("LUNA_CLOUD_MODE") == "1"


def valid_configuration(environ=None):
    env = os.environ if environ is None else environ
    token = env.get("LUNA_OWNER_TOKEN", "")
    origin = env.get("LUNA_PUBLIC_ORIGIN", "")
    if len(token) < MIN_SECRET_LENGTH or token.strip() != token:
        return False
    if not origin:
        return False
    parsed = urlsplit(origin)
    return (parsed.scheme == "https" and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 443) and not parsed.path.rstrip("/")
            and not parsed.query and not parsed.fragment)


def owner_token_valid(header, environ=None):
    env = os.environ if environ is None else environ
    expected = env.get("LUNA_OWNER_TOKEN", "")
    if not valid_configuration(env):
        return False
    if not isinstance(header, str) or not header.startswith("Bearer "):
        return False
    supplied = header[7:]
    return hmac.compare_digest(supplied, expected)


def permitted_origin(headers, environ=None):
    env = os.environ if environ is None else environ
    expected = env.get("LUNA_PUBLIC_ORIGIN", "")
    origin = headers.get("origin")
    # Browser writes must have an Origin. Non-browser API clients use bearer
    # auth without Origin, and therefore cannot rely on ambient cookies.
    return origin is None or hmac.compare_digest(origin, expected)


def _same_origin(value, request, *, referer=False):
    """Compare real origin components, never substring-match hostnames."""
    try:
        parsed = urlsplit(value)
        actual = request.url
        def port(parts):
            if parts.port is not None:
                return parts.port
            return 443 if parts.scheme == "https" else 80
        if (not referer and (parsed.path not in ("", "/")
                             or parsed.query or parsed.fragment)):
            return False
        return bool(
            parsed.scheme in ("http", "https")
            and parsed.scheme == actual.scheme
            and parsed.hostname == actual.hostname
            and port(parsed) == port(actual)
            and parsed.username is None and parsed.password is None
        )
    except (ValueError, TypeError):
        return False


def _local_request_allowed(request):
    """Reject cross-site browser traffic and host-header DNS rebinding.

    Bare-origin-less local API clients are retained for compatibility; they
    cannot by themselves establish an authenticated owner identity.
    """
    try:
        hostname = request.url.hostname
    except (ValueError, TypeError):
        return False
    if hostname not in LOOPBACK:
        # Starlette's synthetic hostname is allowed only in its test client,
        # never as an alternate production hostname.
        synthetic = (hostname == "testserver" and request.client is not None
                     and request.client.host == "testclient")
        if not synthetic:
            return False
    if request.headers.get("sec-fetch-site", "").lower() not in ("", "none", "same-origin"):
        return False
    origin = request.headers.get("origin")
    if origin is not None and not _same_origin(origin, request):
        return False
    referrer = request.headers.get("referer")
    if referrer is not None and not _same_origin(referrer, request, referer=True):
        return False
    return True


class CloudOwnerGate(BaseHTTPMiddleware):
    """Optional outer access boundary; never accepts unauthenticated traffic."""

    async def dispatch(self, request, call_next):
        if not cloud_mode():
            if not _local_request_allowed(request):
                return JSONResponse(
                    {"detail": "Same-origin loopback access required"}, status_code=403
                )
            return await call_next(request)
        if not valid_configuration():
            return JSONResponse({"detail": "Cloud owner gate is not configured"}, status_code=503)
        if request.url.scheme != "https":
            # A TLS-terminating reverse proxy must set a trusted ASGI scheme;
            # don't trust arbitrary X-Forwarded-Proto headers from clients.
            return JSONResponse({"detail": "HTTPS required"}, status_code=403)
        if not owner_token_valid(request.headers.get("authorization")):
            return JSONResponse({"detail": "Owner authorization required"}, status_code=401)
        if request.method not in SAFE_METHODS and not permitted_origin(request.headers):
            return JSONResponse({"detail": "Origin not permitted"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
