"""Per-request correlation context (Sprint 24 — API hardening).

A single request-scoped id that ties every log line, the response header, and any
error body for one request together. It is carried in a :class:`ContextVar` so any
code — a deep service, a repository, an exception handler — can read it without it
being threaded through every call, and a logging filter stamps it onto every
record so the existing log format gains correlation without callers changing.

Nothing here is business logic; it is pure observability plumbing. Outside a
request (startup, shutdown, a background job) the id reads as ``"-"``.
"""

import contextvars
import logging

#: The canonical correlation header, echoed on every response and honoured on
#: input so a trusted caller (a gateway, a test) can supply its own id.
REQUEST_ID_HEADER = "X-Request-ID"

#: The current request's id, or ``"-"`` when there is no request in scope.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def get_request_id() -> str:
    """Return the current request's correlation id, or ``"-"`` outside a request."""
    return request_id_var.get()


class RequestIdLogFilter(logging.Filter):
    """Stamps the current request id onto every log record.

    Attached to the root handler so ``%(request_id)s`` in the log format always
    resolves — inside a request to that request's id, outside one to ``"-"`` —
    which is what lets one request's log lines be grepped together.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
