"""Vector store provider contract (Sprint 10.2 — infrastructure abstraction).

Defines the replaceable vector-store interface: a health check plus collection-
management primitives. Concrete providers (e.g. Qdrant) own all vendor-specific
code behind this interface, isolated from services, repositories, models, and
routers.

Sprint 10.2 shipped infrastructure only (health check + collection primitives).
Sprint 10.3 added ``upsert_vector`` (indexing). Sprint 10.4 adds ONE capability
— ``search_vectors`` — returning ``(point_id, score)`` pairs ordered by
similarity. There is still NO hybrid/keyword search, NO reranking, NO metadata
filtering, NO recommend/scroll/query, and NO batch search: those belong to later
sprints and are intentionally absent from this contract. Providers must return
plain ``(str, float)`` tuples — never vendor/SDK objects.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple


class VectorStoreError(Exception):
    """Raised when a vector-store operation fails.

    Wraps provider/client failures so vendor internals never leak past the
    provider boundary.
    """


class VectorStoreProvider(ABC):
    """Replaceable vector-store strategy (infrastructure primitives only).

    Concrete implementations live behind this interface so the rest of the
    system stays vendor-agnostic. Distance metrics are expressed as
    vendor-neutral strings (e.g. ``"Cosine"``); each provider maps them to its
    own representation.
    """

    name: str

    @abstractmethod
    def health_check(self) -> bool:
        """Return ``True`` if the vector store is reachable, else ``False``."""

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        """Return whether a collection named ``collection_name`` exists."""

    @abstractmethod
    def create_collection(
        self, collection_name: str, vector_size: int, distance: str = "Cosine"
    ) -> None:
        """Create a collection sized for ``vector_size``-dimensional vectors.

        ``distance`` is a vendor-neutral metric name; concrete providers map it
        to their own enum. No vectors are indexed here — this only provisions
        the collection.
        """

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        """Delete the collection named ``collection_name``."""

    @abstractmethod
    def upsert_vector(
        self,
        collection_name: str,
        point_id: str,
        vector: List[float],
        payload: Dict[str, object],
    ) -> None:
        """Insert or update a single vector point (Sprint 10.3, indexing only).

        Writes one point (``point_id`` + ``vector`` + ``payload``) into
        ``collection_name``. This is an index write only — it performs no
        search, query, or similarity lookup.
        """

    @abstractmethod
    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int,
    ) -> List[Tuple[str, float]]:
        """Return the ``limit`` most similar points (Sprint 10.4).

        Returns ``[(point_id, score), ...]`` ordered by descending similarity —
        plain ``(str, float)`` tuples only, never vendor/SDK objects and never
        payloads. Pure similarity search: no hybrid/keyword matching, reranking,
        or metadata filtering.
        """
