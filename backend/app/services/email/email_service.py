"""Transactional email service (Sprint 18.1A).

The seam between authentication and email delivery. Callers ask for a
*business* email ("send this user their verification code"); the service
renders the template and hands the result to the injected provider.

Authentication never sees a provider, a template, or SMTP. Adding invitation
emails later means one method here plus one template — no change to the
provider contract or to any caller.

Delivery failures are surfaced to the caller, which decides the policy; the
service itself never swallows them.
"""

from urllib.parse import quote

from app.services.email.models import EmailMessage
from app.services.email.providers.base import EmailProvider
from app.services.email.templates import (
    render_password_reset_email,
    render_verification_email,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Renders and dispatches the platform's transactional emails."""

    def __init__(
        self,
        provider: EmailProvider,
        *,
        product_name: str,
        frontend_base_url: str,
    ) -> None:
        self.provider = provider
        self.product_name = product_name
        self.frontend_base_url = frontend_base_url.rstrip("/")

    # --- Public API ------------------------------------------------------

    def send_verification_email(
        self, *, to: str, code: str, expires_minutes: int
    ) -> None:
        """Deliver a one-time email-verification code."""
        message = render_verification_email(
            to=to,
            code=code,
            product_name=self.product_name,
            expires_minutes=expires_minutes,
        )
        self._send(message, kind="verification")

    def send_password_reset_email(
        self, *, to: str, token: str, expires_minutes: int
    ) -> None:
        """Deliver a single-use password-reset link."""
        message = render_password_reset_email(
            to=to,
            reset_url=self.build_reset_url(token),
            product_name=self.product_name,
            expires_minutes=expires_minutes,
        )
        self._send(message, kind="password_reset")

    def build_reset_url(self, token: str) -> str:
        """Absolute URL of the frontend reset page for ``token``."""
        return f"{self.frontend_base_url}/reset-password?token={quote(token, safe='')}"

    # --- Internals -------------------------------------------------------

    def _send(self, message: EmailMessage, *, kind: str) -> None:
        # The recipient is logged; the code/token inside the body never is.
        logger.info(
            "Sending %s email to %s via %s", kind, message.to, self.provider.name
        )
        self.provider.send(message)
