"""Conversation generation provider contract.

Defines the replaceable provider interface and the domain errors the API maps
to 502/504. Concrete providers (e.g. Claude) implement ``generate_reply`` and
own all vendor-specific code. No ownership logic or repository access here.
"""

from abc import ABC, abstractmethod

from app.models.blueprint import Blueprint
from app.schemas.conversation_context import ConversationContextResponse


class ConversationGenerationError(Exception):
    """Raised when a provider fails to produce a reply.

    Covers provider/API failures and empty responses. The API maps this to
    ``502 Bad Gateway``. Provider internals (e.g. Anthropic exception details)
    must not be attached.
    """


class ConversationGenerationTimeoutError(ConversationGenerationError):
    """Raised when a provider call times out. Mapped to ``504``."""


class ConversationProvider(ABC):
    """Replaceable strategy that turns a blueprint + context into a reply."""

    name: str

    @abstractmethod
    def generate_reply(
        self,
        blueprint: Blueprint,
        context: ConversationContextResponse,
    ) -> str:
        """Produce the next assistant reply as plain text."""
