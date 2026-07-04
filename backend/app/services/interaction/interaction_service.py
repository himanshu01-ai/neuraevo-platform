"""Interaction Service (Sprint 12.1 — stateless delegator).

Receives an :class:`InteractionRequest`, delegates normalization to an injected
:class:`InteractionProvider`, and returns the provider's
:class:`InteractionResult` unchanged. That is its entire responsibility.

It performs NO modality handling, speech recognition/synthesis, OCR, document
parsing, AI inference, streaming, planning, permission checks, tool execution,
retries, logging, repository usage, or runtime coordination. The provider is
injected via the constructor (never instantiated here). No concrete provider
exists yet — real modality processing is a later sprint.
"""

from app.services.interaction.models import (
    InteractionRequest,
    InteractionResult,
)
from app.services.interaction.providers.base import InteractionProvider


class InteractionService:
    """Delegates interaction processing to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: InteractionProvider) -> None:
        self.provider = provider

    def process_interaction(
        self, request: InteractionRequest
    ) -> InteractionResult:
        """Return the provider's result for ``request``, unchanged.

        The request is passed to the provider untouched and the returned result
        is handed back to the caller as-is. Provider exceptions propagate
        unchanged. Nothing is recognized, synthesized, parsed, or executed.
        """
        return self.provider.process_interaction(request)
