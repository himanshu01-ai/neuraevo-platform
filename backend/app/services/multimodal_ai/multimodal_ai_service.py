"""Multimodal AI Service (Sprint 12.2 — stateless delegator).

Receives a :class:`MultimodalAIRequest`, delegates generation to an injected
:class:`MultimodalAIProvider`, and returns the provider's
:class:`MultimodalAIResponse` unchanged. That is its entire responsibility.

It performs NO retries, caching, logging, streaming, parsing, prompt building,
memory access, planning, permission checks, tool execution, or runtime
coordination. The provider is injected via the constructor (never instantiated
here). No concrete provider exists yet — real generation is a later sprint.
"""

from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)
from app.services.multimodal_ai.providers.base import MultimodalAIProvider


class MultimodalAIService:
    """Delegates multimodal AI generation to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: MultimodalAIProvider) -> None:
        self.provider = provider

    def generate_response(
        self, request: MultimodalAIRequest
    ) -> MultimodalAIResponse:
        """Return the provider's response for ``request``, unchanged.

        The request is passed to the provider untouched and the returned response
        is handed back to the caller as-is. Provider exceptions propagate
        unchanged. Nothing is retried, cached, streamed, parsed, or orchestrated.
        """
        return self.provider.generate_response(request)
