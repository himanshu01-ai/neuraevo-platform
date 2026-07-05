"""Multimodal AI adapters package (Sprint 12.3 abstraction; 12.5 Gemini adapter).

Exposes the abstract :class:`MultimodalAIAdapter` contract, the first concrete
:class:`GeminiAdapter` (the ONLY module in the app that touches the
``google-genai`` SDK), the :class:`GenAIClientProtocol` structural interface the
adapter depends on instead of the concrete SDK class, the
:func:`create_genai_client` factory the composition root uses to build the real
client, and :data:`MODEL_METADATA_KEY` — the request-metadata key through which
the provider hands the adapter its model name.
"""

from app.services.multimodal_ai.adapters.base import MultimodalAIAdapter
from app.services.multimodal_ai.adapters.gemini_adapter import (
    MODEL_METADATA_KEY,
    GeminiAdapter,
    GenAIClientProtocol,
    GenAIModelsProtocol,
    create_genai_client,
)

__all__ = [
    "MultimodalAIAdapter",
    "GeminiAdapter",
    "GenAIClientProtocol",
    "GenAIModelsProtocol",
    "create_genai_client",
    "MODEL_METADATA_KEY",
]
