"""Multimodal AI adapters package (Sprint 12.3 — abstraction only).

Exposes the abstract :class:`MultimodalAIAdapter` contract that future concrete
adapters (owning the vendor SDK / networking / streaming) will implement beneath
the Sprint 12.2 :class:`MultimodalAIProvider`. No concrete adapter is
implemented in this sprint — only the interface future sprints will implement.
Nothing is wired.
"""

from app.services.multimodal_ai.adapters.base import MultimodalAIAdapter

__all__ = ["MultimodalAIAdapter"]
