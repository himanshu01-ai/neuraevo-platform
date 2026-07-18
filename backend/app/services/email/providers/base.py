"""Email provider contract (Sprint 18.1A).

Defines the replaceable delivery interface. Concrete providers own all
transport-specific code (SMTP, and later hosted APIs such as SES/Postmark),
isolated from services, repositories, models, and routers. Authentication
never imports a provider — it depends on :class:`~app.services.email.EmailService`.
"""

from abc import ABC, abstractmethod

from app.services.email.models import EmailMessage


class EmailDeliveryError(Exception):
    """Raised when a provider cannot deliver a message."""


class EmailProvider(ABC):
    """Replaceable strategy that delivers a rendered :class:`EmailMessage`."""

    name: str

    @abstractmethod
    def send(self, message: EmailMessage) -> None:
        """Deliver ``message``.

        Raises :class:`EmailDeliveryError` if delivery fails. Providers do not
        retry, queue, or template — they deliver exactly once per call.
        """
