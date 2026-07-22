"""Global exception handlers — one JSON error contract for every path (Sprint 24).

Before this, an exception a router did not catch reached Starlette's default 500,
which returns ``text/plain "Internal Server Error"`` (or a traceback in debug) —
not the ``{"detail": ...}`` JSON every handled error uses, and the one shape the
frontend's error normaliser reads. These handlers close that gap: **every**
failure — a validation 422, a raised ``HTTPException``, or a wholly unexpected
error — now returns the same ``{"detail": ...}`` JSON, and every response carries
the request's correlation id.

Nothing about the handled 4xx contract changes: the 422 body keeps FastAPI's
exact ``detail``-list shape, and an ``HTTPException``'s ``detail`` and headers are
passed through unchanged. The only new behaviour is the safety net for genuinely
unexpected errors, which are logged with their traceback server-side and reported
to the client as a generic sentence — the internals are never leaked (a debug
build may include the exception type to aid local work).
"""

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.request_context import REQUEST_ID_HEADER, get_request_id
from app.utils.logger import get_logger

logger = get_logger("app.error")


def _request_id(request: Request) -> str:
    """The request's correlation id — from request state, falling back to the ctx."""
    return getattr(request.state, "request_id", None) or get_request_id()


def _headers(request: Request, extra: dict | None = None) -> dict:
    headers = dict(extra or {})
    headers[REQUEST_ID_HEADER] = _request_id(request)
    return headers


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 with FastAPI's exact field-level ``detail`` list — shape unchanged.

    Reproduces the framework default so the frontend's validation handling keeps
    working byte for byte; the only addition is the correlation header.
    """
    # 422 literal (not status.HTTP_422_UNPROCESSABLE_ENTITY, which Starlette has
    # deprecated) — the numeric code is stable and avoids the deprecation.
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
        headers=_headers(request),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """A raised ``HTTPException`` → ``{"detail": ...}`` with its status and headers.

    Reproduces the framework default (``detail`` and any ``headers`` — e.g. a
    401's ``WWW-Authenticate`` — pass through unchanged) plus the correlation
    header, so every handled error shares the one JSON contract.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=_headers(request, exc.headers),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """The safety net: any uncaught exception → a logged, non-leaking 500 JSON.

    The traceback is logged server-side with the request's id (so an operator can
    find it from the id the client was given) and never returned. A debug build
    appends the exception type to the client sentence to speed local diagnosis;
    a production build returns only the generic sentence.
    """
    request_id = _request_id(request)
    logger.exception(
        "unhandled exception request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    detail = "An unexpected error occurred. Please try again."
    if settings.DEBUG:
        detail = f"{detail} [{type(exc).__name__}: {exc}]"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
        headers=_headers(request),
    )


def register_exception_handlers(app) -> None:
    """Register all handlers on the app (called from the application factory).

    ``StarletteHTTPException`` covers FastAPI's ``HTTPException`` too (it is a
    subclass), so both the framework's own 404/405 and every router's raised
    error share the one shape.
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
