"""Vector store package (Sprint 10.2 — Qdrant infrastructure).

Ships the vector-store abstraction and its Qdrant implementation: the
:class:`VectorStoreService` delegator, the abstract :class:`VectorStoreProvider`
(+ :class:`VectorStoreError`), and the concrete :class:`QdrantProvider`. This is
infrastructure only — no indexing, no vector search, no embedding generation,
and no retrieval/persistence integration. Those belong to later sprints.
"""

from app.services.vector_store.providers import (
    QdrantProvider,
    VectorStoreError,
    VectorStoreProvider,
)
from app.services.vector_store.vector_store_service import VectorStoreService

__all__ = [
    "VectorStoreService",
    "VectorStoreProvider",
    "VectorStoreError",
    "QdrantProvider",
]
