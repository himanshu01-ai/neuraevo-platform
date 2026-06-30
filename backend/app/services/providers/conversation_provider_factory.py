"""Conversation provider factory.

Returns the active :class:`ConversationProvider` for conversation generation.
Introduced in Sprint 6E to decouple :class:`ConversationGenerationService` from
any concrete provider: the service asks this factory for a provider instead of
holding one. Today it always returns a :class:`ClaudeConversationProvider`;
selecting or swapping providers later is a change confined to this factory.

Stateless: holds only immutable connection settings and constructs the provider
on demand. No business logic, no AI logic, no prompt construction — provider
selection only.
"""

from typing import Optional

from app.services.providers.claude_conversation_provider import (
    ClaudeConversationProvider,
)
from app.services.providers.conversation_provider import ConversationProvider


class ConversationProviderFactory:
    """Provides the active conversation provider (currently always Claude)."""

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str,
        timeout: float = 30.0,
        max_tokens: int = 4096,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens

    def get_provider(self) -> ConversationProvider:
        """Return the active conversation provider.

        Currently always a :class:`ClaudeConversationProvider`, built from the
        configured Anthropic settings. Any future provider-selection logic
        belongs here and nowhere else, keeping callers provider-agnostic.
        """
        return ClaudeConversationProvider(
            api_key=self._api_key,
            model=self._model,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
        )
