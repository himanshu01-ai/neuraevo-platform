"""SMTP email provider (Sprint 18.1A).

The only module in the codebase that imports ``smtplib``. Connection settings
are injected from the composition root; the provider holds no business logic
and performs no templating.
"""

import smtplib
from email.message import EmailMessage as MIMEEmailMessage
from typing import Optional

from app.services.email.models import EmailMessage
from app.services.email.providers.base import EmailDeliveryError, EmailProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SMTPEmailProvider(EmailProvider):
    """Delivers email through an SMTP server."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        from_name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.from_address = from_address
        self.from_name = from_name
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout

    def _build(self, message: EmailMessage) -> MIMEEmailMessage:
        mime = MIMEEmailMessage()
        mime["From"] = f"{self.from_name} <{self.from_address}>"
        mime["To"] = message.to
        mime["Subject"] = message.subject
        # Plain text first, HTML as the richer alternative — clients that
        # cannot render HTML fall back to the text part.
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")
        return mime

    def send(self, message: EmailMessage) -> None:
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as client:
                if self.use_tls:
                    client.starttls()
                if self.username and self.password:
                    client.login(self.username, self.password)
                client.send_message(self._build(message))
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("SMTP delivery to %s failed: %s", message.to, exc)
            raise EmailDeliveryError(str(exc)) from exc
