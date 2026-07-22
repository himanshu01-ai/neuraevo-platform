"""Centralized logging configuration.

Provides :func:`configure_logging` to initialize the root logger once at
application startup and :func:`get_logger` to retrieve named loggers
throughout the codebase.
"""

import logging
import sys

from app.core.config import settings
from app.core.request_context import RequestIdLogFilter

# ``%(request_id)s`` is supplied by ``RequestIdLogFilter`` (Sprint 24), so every
# line carries the correlation id of the request that produced it — ``-`` outside
# a request. The filter guarantees the attribute exists, so the format never
# raises for a record logged before any request.
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging() -> None:
    """Configure the root logger.

    Safe to call multiple times; configuration is applied only once.
    """
    global _configured
    if _configured:
        return

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))
    # The filter stamps the correlation id onto every record the handler emits,
    # so ``%(request_id)s`` in the format always resolves.
    handler.addFilter(RequestIdLogFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring logging has been configured."""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
