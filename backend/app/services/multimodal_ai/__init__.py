"""Multimodal AI package (Sprint 12.2 — Multimodal AI Provider framework).

Ships ONLY the multimodal AI abstraction: the provider-independent
:class:`MultimodalAIRequest` / :class:`MultimodalAIResponse` models, the abstract
:class:`MultimodalAIProvider` contract, and the stateless
:class:`MultimodalAIService` delegator. It consumes the Sprint 12.1 Interaction
layer's normalized output shape but is not wired into the Runtime, AI
Orchestrator, Planner, Interaction, or any API route. No concrete provider, SDK,
HTTP client, websocket, streaming, networking, prompt building, or model call —
those belong to later sprints.
"""

from app.services.multimodal_ai.models import (
    MultimodalAIRequest,
    MultimodalAIResponse,
)
from app.services.multimodal_ai.multimodal_ai_service import MultimodalAIService
from app.services.multimodal_ai.providers import MultimodalAIProvider

__all__ = [
    "MultimodalAIService",
    "MultimodalAIProvider",
    "MultimodalAIRequest",
    "MultimodalAIResponse",
]
