"""Transactional email (Sprint 18.1A).

Authentication depends on :class:`EmailService` only; providers are wired in
the composition root (``app.core.dependencies``).
"""

from app.services.email.email_service import EmailService
from app.services.email.models import EmailMessage
from app.services.email.providers import (
    ConsoleEmailProvider,
    EmailDeliveryError,
    EmailProvider,
    SMTPEmailProvider,
)

__all__ = [
    "ConsoleEmailProvider",
    "EmailDeliveryError",
    "EmailMessage",
    "EmailProvider",
    "EmailService",
    "SMTPEmailProvider",
]
