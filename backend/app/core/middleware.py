"""Request-context middleware — correlation + timing (Sprint 24 — API hardening).

Wraps every request so that, before the route runs, a correlation id exists (the
caller's ``X-Request-ID`` if supplied and well-formed, otherwise a fresh one) and
is placed both on ``request.state`` (for the exception handlers) and in the
:class:`~app.core.request_context.request_id_var` context (for the logging
filter). After the route runs it stamps the id and the elapsed time onto the
response headers and writes one structured access line.

It owns no business logic and reads no body: it only observes. Timing uses a
monotonic clock so a wall-clock adjustment can't produce a negative duration.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.request_context import REQUEST_ID_HEADER, request_id_var
from app.utils.logger import get_logger

logger = get_logger("app.access")

#: The longest a client-supplied id we will echo; anything longer or with odd
#: characters is replaced, so a header can't be used to inject into logs.
_MAX_ID_LENGTH = 128


def _clean_incoming_id(value: str | None) -> str | None:
    """Accept a caller's id only if it is short and printable-simple."""
    if not value:
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > _MAX_ID_LENGTH:
        return None
    if not all(c.isalnum() or c in "-_." for c in candidate):
        return None
    return candidate


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a correlation id, times the request, and logs its completion."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = _clean_incoming_id(
            request.headers.get(REQUEST_ID_HEADER)
        ) or uuid.uuid4().hex
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # The correlation id is still in scope, so the id in this line matches
            # the one the client will receive from the 500 handler upstream.
            duration_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "http_request method=%s path=%s status=500 duration_ms=%.1f request_id=%s",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
            )
            request_id_var.reset(token)
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time-ms"] = f"{duration_ms:.1f}"
        logger.info(
            "http_request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        request_id_var.reset(token)
        return response
