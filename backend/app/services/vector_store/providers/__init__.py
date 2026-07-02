"""Vector store providers package (Sprint 10.2 — infrastructure).

Exposes the abstract :class:`VectorStoreProvider` contract, its
:class:`VectorStoreError`, and the concrete :class:`QdrantProvider`. All
Qdrant-specific code is isolated inside :class:`QdrantProvider`.
"""

from app.services.vector_store.providers.base import (
    VectorStoreError,
    VectorStoreProvider,
)
from app.services.vector_store.providers.qdrant_provider import QdrantProvider

__all__ = ["VectorStoreProvider", "VectorStoreError", "QdrantProvider"]
