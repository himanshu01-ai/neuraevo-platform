"""Provider-independent email value objects (Sprint 18.1A)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    """One outbound email, already rendered.

    Providers receive this and are responsible only for delivery — never for
    templating, business rules, or deciding whether to send.
    """

    to: str
    subject: str
    html_body: str
    text_body: str

    def __post_init__(self) -> None:
        if not self.to:
            raise ValueError("EmailMessage.to must not be empty")
        if not self.subject:
            raise ValueError("EmailMessage.subject must not be empty")
