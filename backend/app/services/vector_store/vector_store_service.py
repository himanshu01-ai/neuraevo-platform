"""Vector Store Service (Sprint 10.2 — infrastructure delegator).

Stateless service that delegates vector-store infrastructure operations (health
check and collection-management primitives) to an injected
:class:`VectorStoreProvider`, returning provider results unchanged.

It performs NO vector search, NO embedding generation, NO repository usage, and
NO AI logic. As of Sprint 10.3 it delegates a single index write —
``upsert_vector`` — used by memory persistence to index a saved memory; there is
still no search, query, or similarity lookup. The provider is injected via the
constructor (never instantiated here).
"""

from typing import Dict, List

from app.services.vector_store.providers.base import VectorStoreProvider


class VectorStoreService:
    """Delegates vector-store infrastructure calls to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: VectorStoreProvider) -> None:
        self.provider = provider

    def health_check(self) -> bool:
        """Return whether the underlying vector store is reachable."""
        return self.provider.health_check()

    def collection_exists(self, collection_name: str) -> bool:
        """Return whether ``collection_name`` exists in the vector store."""
        return self.provider.collection_exists(collection_name)

    def create_collection(
        self, collection_name: str, vector_size: int, distance: str = "Cosine"
    ) -> None:
        """Provision a collection sized for ``vector_size``-dim vectors."""
        return self.provider.create_collection(
            collection_name, vector_size, distance
        )

    def delete_collection(self, collection_name: str) -> None:
        """Delete the collection named ``collection_name``."""
        return self.provider.delete_collection(collection_name)

    def upsert_vector(
        self,
        collection_name: str,
        point_id: str,
        vector: List[float],
        payload: Dict[str, object],
    ) -> None:
        """Index one vector point (Sprint 10.3) — index write only, no search."""
        return self.provider.upsert_vector(
            collection_name, point_id, vector, payload
        )
