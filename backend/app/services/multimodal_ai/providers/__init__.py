"""Multimodal AI providers package (Sprint 12.2 — abstraction only).

Exposes the abstract :class:`MultimodalAIProvider` contract. No concrete
multimodal AI provider is implemented in this sprint — only the interface future
sprints will implement.
"""

from app.services.multimodal_ai.providers.base import MultimodalAIProvider

__all__ = ["MultimodalAIProvider"]
