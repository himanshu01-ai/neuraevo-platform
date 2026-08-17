"""Security response headers (Sprint 25 — security hardening).

Adds a standard set of hardening headers to every response — including error
responses, since it runs as an outer middleware and stamps the response on the
way out. All values are configuration-driven (see ``Settings``), so a deployment
can tune the policy without a code change, and nothing here changes a response
body or status.

The Content-Security-Policy is deliberately restrictive: this is a JSON API that
serves none of its own HTML, so ``default-src 'none'`` is safe and blocks a
sniffed HTML response from loading anything. HSTS is emitted **only in
production and only over HTTPS**, so it can never pin an http development host —
sending it over plain http, or in development, would be a footgun rather than a
protection.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.config import settings


def _client_uses_https(request: Request) -> bool:
    """Whether the original client connection was HTTPS.

    Honours ``X-Forwarded-Proto`` because in a normal deployment TLS is
    terminated at a proxy and the app sees http; the proxy reports the real
    scheme in that header.
    """
    forwarded = request.headers.get("x-forwarded-proto", "")
    if forwarded:
        # May be a comma-separated list; the first entry is the client-facing one.
        return forwarded.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies configured security headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not settings.SECURITY_HEADERS_ENABLED:
            return response

        headers = response.headers
        # setdefault so an endpoint that intentionally sets its own value (e.g. a
        # future embeddable view relaxing frame-ancestors) is never overridden.
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", settings.SECURITY_REFERRER_POLICY)
        headers.setdefault("Permissions-Policy", settings.SECURITY_PERMISSIONS_POLICY)
        headers.setdefault("Content-Security-Policy", settings.SECURITY_CSP)

        # HSTS: production + HTTPS only, so a development http host is never pinned.
        if settings.is_production and _client_uses_https(request):
            value = f"max-age={settings.HSTS_MAX_AGE_SECONDS}"
            if settings.HSTS_INCLUDE_SUBDOMAINS:
                value += "; includeSubDomains"
            headers.setdefault("Strict-Transport-Security", value)

        return response
