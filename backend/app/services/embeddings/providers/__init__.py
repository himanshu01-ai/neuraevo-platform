"""Embedding providers package (Sprint 10.1 — abstraction only).

Exposes the abstract :class:`EmbeddingProvider` contract. No concrete provider
(OpenAI / Voyage / Jina / Gemini / Cohere) is implemented in this sprint — only
the interface future sprints will implement.
"""

from app.services.embeddings.providers.base import EmbeddingProvider

__all__ = ["EmbeddingProvider"]
