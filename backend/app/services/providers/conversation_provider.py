"""Conversation generation provider contract.

Defines the replaceable provider interface and the domain errors the API maps
to 502/504. Concrete providers (e.g. Claude) implement ``generate_reply`` and
own all vendor-specific code. As of Sprint 6D the prompt is built upstream
(``PromptBuilderService``) and passed in fully formed: providers do no prompt
construction, ownership logic, or repository access.
"""

from abc import ABC, abstractmethod


class ConversationGenerationError(Exception):
    """Raised when a provider fails to produce a reply.

    Covers provider/API failures and empty responses. The API maps this to
    ``502 Bad Gateway``. Provider internals (e.g. Anthropic exception details)
    must not be attached.
    """


class ConversationGenerationTimeoutError(ConversationGenerationError):
    """Raised when a provider call times out. Mapped to ``504``."""


class ConversationProvider(ABC):
    """Replaceable strategy that turns a built prompt into a reply."""

    name: str

    @abstractmethod
    def generate_reply(self, prompt: str) -> str:
        """Produce the next assistant reply as plain text from ``prompt``."""
