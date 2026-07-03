"""Qdrant vector-store provider (Sprint 10.2 — production implementation).

Implements :class:`VectorStoreProvider` against a Qdrant instance: it creates/
manages the Qdrant client, performs a health check, and exposes collection-
management primitives. All Qdrant-specific code is contained here — no indexing,
no vector search, no embedding generation, and no Qdrant code anywhere else.

The ``qdrant_client`` SDK is imported lazily (inside the client-construction,
collection-creation, and upsert paths), so importing this module never requires
the package to be installed. A client may also be injected for testing. Search
results are converted to plain ``(str, float)`` tuples here, so no Qdrant SDK
object ever crosses the provider boundary.
"""

from typing import Dict, List, Optional, Tuple

from app.services.vector_store.providers.base import (
    VectorStoreError,
    VectorStoreProvider,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QdrantProvider(VectorStoreProvider):
    """Manages a Qdrant client and collection-lifecycle primitives."""

    name = "qdrant"

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        client: object = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        # ``client`` allows injecting a stub in tests; otherwise it is built
        # lazily so importing this module never requires qdrant_client or a
        # reachable server.
        self._client = client

    # --- Client ----------------------------------------------------------

    def _get_client(self):
        """Return the Qdrant client, building it lazily on first use."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:  # dependency not installed
                raise VectorStoreError(
                    "qdrant-client is not installed"
                ) from exc
            self._client = QdrantClient(
                url=self.url, api_key=self.api_key, timeout=self.timeout
            )
        return self._client

    # --- Provider interface ---------------------------------------------

    def health_check(self) -> bool:
        """Return ``True`` if Qdrant is reachable, else ``False``.

        Never raises: any client/connection failure (unreachable server,
        misconfiguration, or a missing SDK) is logged and reported as ``False``
        so callers can treat the store as simply unavailable.
        """
        try:
            self._get_client().get_collections()
            return True
        except Exception as exc:  # unreachable / misconfigured / not installed
            logger.warning("Qdrant health check failed: %s", exc)
            return False

    def collection_exists(self, collection_name: str) -> bool:
        """Delegate to the client; wrap any failure as :class:`VectorStoreError`."""
        try:
            return self._get_client().collection_exists(collection_name)
        except Exception as exc:
            logger.warning("Qdrant collection_exists failed: %s", exc)
            raise VectorStoreError("collection_exists failed") from exc

    def create_collection(
        self, collection_name: str, vector_size: int, distance: str = "Cosine"
    ) -> None:
        """Provision a collection (no vectors indexed).

        Maps the vendor-neutral ``distance`` string to Qdrant's ``Distance``
        enum (lazily imported) and calls the client. Failures are wrapped as
        :class:`VectorStoreError`.
        """
        try:
            from qdrant_client.models import Distance, VectorParams

            self._get_client().create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size, distance=Distance(distance)
                ),
            )
        except Exception as exc:
            logger.warning("Qdrant create_collection failed: %s", exc)
            raise VectorStoreError("create_collection failed") from exc

    def delete_collection(self, collection_name: str) -> None:
        """Delegate to the client; wrap any failure as :class:`VectorStoreError`."""
        try:
            self._get_client().delete_collection(collection_name)
        except Exception as exc:
            logger.warning("Qdrant delete_collection failed: %s", exc)
            raise VectorStoreError("delete_collection failed") from exc

    def upsert_vector(
        self,
        collection_name: str,
        point_id: str,
        vector: List[float],
        payload: Dict[str, object],
    ) -> None:
        """Write one point into ``collection_name`` (index only, no search).

        Wraps the id/vector/payload in a Qdrant ``PointStruct`` (lazily
        imported) and calls ``client.upsert``. Failures are wrapped as
        :class:`VectorStoreError`.
        """
        try:
            from qdrant_client.models import PointStruct

            self._get_client().upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=point_id, vector=vector, payload=payload
                    )
                ],
            )
        except Exception as exc:
            logger.warning("Qdrant upsert_vector failed: %s", exc)
            raise VectorStoreError("upsert_vector failed") from exc

    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int,
    ) -> List[Tuple[str, float]]:
        """Return the ``limit`` most similar points as ``(id, score)`` tuples.

        Calls the Qdrant client's similarity search and converts each scored
        point into a plain ``(str, float)`` tuple, so no Qdrant SDK object (or
        payload) escapes this provider. Failures are wrapped as
        :class:`VectorStoreError`.
        """
        try:
            results = self._get_client().search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
            )
            return [(str(point.id), float(point.score)) for point in results]
        except Exception as exc:
            logger.warning("Qdrant search_vectors failed: %s", exc)
            raise VectorStoreError("search_vectors failed") from exc
