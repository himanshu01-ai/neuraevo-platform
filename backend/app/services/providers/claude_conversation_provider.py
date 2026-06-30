"""Claude (Anthropic) conversation generation provider.

Implements :class:`ConversationProvider` by sending a fully built prompt
(constructed upstream by ``PromptBuilderService``, Sprint 6D) to the Anthropic
Messages API and returning the generated reply. All Claude-specific logic is
contained here — no prompt construction, no ownership logic, no repository
access, and no Anthropic code anywhere else.
"""

from typing import Optional

import anthropic

from app.services.providers.conversation_provider import (
    ConversationGenerationError,
    ConversationGenerationTimeoutError,
    ConversationProvider,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an AI employee responding within an ongoing conversation. Stay in "
    "character according to the provided blueprint. Reply with plain text only "
    "— no JSON, no markdown wrappers, no role labels."
)


class ClaudeConversationProvider(ConversationProvider):
    """Generates a conversation reply using Anthropic's Claude models."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str,
        timeout: float = 30.0,
        max_tokens: int = 4096,
        client: Optional["anthropic.Anthropic"] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        # ``client`` allows injecting a stub in tests; otherwise it is built
        # lazily so importing this module never requires a configured key.
        self._client = client

    # --- Client ----------------------------------------------------------

    def _get_client(self) -> "anthropic.Anthropic":
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=self.api_key, timeout=self.timeout
            )
        return self._client

    # --- Provider interface ---------------------------------------------

    def generate_reply(self, prompt: str) -> str:
        """Send the already-built ``prompt`` to Claude and return the reply.

        The prompt is constructed upstream by ``PromptBuilderService``; this
        method performs Claude API communication only. Raises
        :class:`ConversationGenerationTimeoutError` on timeout and
        :class:`ConversationGenerationError` on any other failure (API error or
        empty response).
        """
        try:
            client = self._get_client()
        except Exception as exc:  # missing key / misconfiguration
            logger.warning("Claude client initialization failed: %s", exc)
            raise ConversationGenerationError(
                "Claude client unavailable"
            ) from exc

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APITimeoutError as exc:
            logger.warning("Claude conversation request timed out")
            raise ConversationGenerationTimeoutError(
                "Conversation generation timed out"
            ) from exc
        except anthropic.APIError as exc:
            logger.warning("Claude API error: %s", exc)
            raise ConversationGenerationError(
                "Claude API request failed"
            ) from exc
        except Exception as exc:  # defensive — never leak internals
            logger.warning("Unexpected Claude failure: %s", exc)
            raise ConversationGenerationError(
                "Conversation generation failed"
            ) from exc

        return self._extract_text(response)

    @staticmethod
    def _extract_text(response) -> str:
        """Concatenate text blocks from the response, rejecting empties."""
        parts: list[str] = []
        for block in getattr(response, "content", None) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", "") or "")
        text = "".join(parts).strip()
        if not text:
            raise ConversationGenerationError(
                "Claude returned an empty response"
            )
        return text
