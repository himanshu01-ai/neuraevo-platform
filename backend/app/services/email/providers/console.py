"""Console email provider (Sprint 18.1A).

Development default: renders the message to the application log instead of
delivering it, so the full verification/reset flow works locally with no SMTP
server. This is a real provider — it always "succeeds" and never silently
swallows a message — but it must not be used in production.
"""

from app.services.email.models import EmailMessage
from app.services.email.providers.base import EmailProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConsoleEmailProvider(EmailProvider):
    """Logs rendered emails rather than sending them."""

    name = "console"

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "[email:console] to=%s subject=%s\n%s",
            message.to,
            message.subject,
            message.text_body,
        )
