"""Multimodal AI providers package (Sprint 12.2 abstraction; 12.4 Gemini provider).

Exposes the abstract :class:`MultimodalAIProvider` contract, the first concrete
business-layer provider :class:`GeminiProvider`, and the immutable
:class:`ProviderConfig` injected into it. ``GeminiProvider`` delegates generation
to an injected :class:`MultimodalAIAdapter` and reads its model name only from
``ProviderConfig`` — it owns no SDK, networking, or streaming.
"""

from app.services.multimodal_ai.providers.base import MultimodalAIProvider
from app.services.multimodal_ai.providers.gemini_provider import (
    GeminiProvider,
    ProviderConfig,
)

__all__ = ["MultimodalAIProvider", "GeminiProvider", "ProviderConfig"]
