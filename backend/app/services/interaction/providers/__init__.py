"""Interaction providers package (Sprint 12.1 — abstraction only).

Exposes the abstract :class:`InteractionProvider` contract. No concrete
interaction provider is implemented in this sprint — only the interface future
sprints will implement.
"""

from app.services.interaction.providers.base import InteractionProvider

__all__ = ["InteractionProvider"]
