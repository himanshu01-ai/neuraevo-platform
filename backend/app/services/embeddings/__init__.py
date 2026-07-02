"""Embeddings package (Sprint 10.1 — semantic memory foundation).

Ships ONLY the embedding abstraction: the :class:`EmbeddingService` delegator
and the abstract :class:`EmbeddingProvider` it delegates to. No concrete
provider, HTTP client, SDK, API key, embedding generation, persistence, or
vector database — those belong to later sprints.
"""

from app.services.embeddings.embedding_service import EmbeddingService
from app.services.embeddings.providers import EmbeddingProvider

__all__ = ["EmbeddingService", "EmbeddingProvider"]
