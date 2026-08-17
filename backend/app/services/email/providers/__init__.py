"""Email delivery providers (Sprint 18.1A)."""

from app.services.email.providers.base import EmailDeliveryError, EmailProvider
from app.services.email.providers.console import ConsoleEmailProvider
from app.services.email.providers.smtp import SMTPEmailProvider

__all__ = [
    "ConsoleEmailProvider",
    "EmailDeliveryError",
    "EmailProvider",
    "SMTPEmailProvider",
]
