"""Unit tests for the Sprint 10.2 Vector Store infrastructure.

Every test mocks the Qdrant client (and, where a real operation touches the
Qdrant models, stubs the ``qdrant_client`` SDK via ``sys.modules``), so no
network, no live server, and no installed SDK are required. Coverage:

* the provider abstraction (``VectorStoreProvider`` is abstract),
* ``QdrantProvider`` delegation for health check + collection primitives, its
  error wrapping, and its lazy-client / missing-SDK behavior,
* ``VectorStoreService`` delegation, statelessness, and constructor DI,
* the composition-root providers resolve.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_vector_store_service
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from app.services.vector_store import (
    QdrantProvider,
    VectorStoreError,
    VectorStoreProvider,
    VectorStoreService,
)
from app.services.vector_store.providers.base import (
    VectorStoreProvider as BaseVectorStoreProvider,
)


# =====================================================================
# Provider abstraction
# =====================================================================
class VectorStoreProviderAbstractionTests(unittest.TestCase):
    def test_provider_is_the_abstract_base(self):
        self.assertIs(VectorStoreProvider, BaseVectorStoreProvider)

    def test_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            VectorStoreProvider()  # abstract methods not implemented

    def test_qdrant_provider_is_a_vector_store_provider(self):
        self.assertTrue(issubclass(QdrantProvider, VectorStoreProvider))


# =====================================================================
# QdrantProvider (client mocked)
# =====================================================================
class QdrantProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock(name="QdrantClient")
        self.provider = QdrantProvider(client=self.client)

    def test_name_is_qdrant(self):
        self.assertEqual(self.provider.name, "qdrant")

    def test_injected_client_is_used(self):
        self.assertIs(self.provider._get_client(), self.client)

    # --- health check ----------------------------------------------------
    def test_health_check_true_when_client_reachable(self):
        self.client.get_collections.return_value = MagicMock()
        self.assertTrue(self.provider.health_check())
        self.client.get_collections.assert_called_once()

    def test_health_check_false_when_client_raises(self):
        self.client.get_collections.side_effect = RuntimeError("unreachable")
        self.assertFalse(self.provider.health_check())

    def test_health_check_false_when_sdk_missing_and_no_client(self):
        # No injected client + qdrant_client not installed -> reported down,
        # never raised (health_check swallows the VectorStoreError).
        provider = QdrantProvider(url="http://localhost:6333")
        self.assertFalse(provider.health_check())

    # --- collection_exists ----------------------------------------------
    def test_collection_exists_delegates_and_returns_value(self):
        self.client.collection_exists.return_value = True
        self.assertTrue(self.provider.collection_exists("memories"))
        self.client.collection_exists.assert_called_once_with("memories")

    def test_collection_exists_wraps_failure(self):
        self.client.collection_exists.side_effect = RuntimeError("boom")
        with self.assertRaises(VectorStoreError):
            self.provider.collection_exists("memories")

    # --- create_collection ----------------------------------------------
    def test_create_collection_delegates_with_mapped_distance(self):
        fake_models = MagicMock(name="qdrant_client.models")
        with patch.dict(
            sys.modules,
            {
                "qdrant_client": MagicMock(name="qdrant_client"),
                "qdrant_client.models": fake_models,
            },
        ):
            self.provider.create_collection("memories", 1536, "Cosine")

        fake_models.Distance.assert_called_once_with("Cosine")
        fake_models.VectorParams.assert_called_once_with(
            size=1536, distance=fake_models.Distance.return_value
        )
        self.client.create_collection.assert_called_once_with(
            collection_name="memories",
            vectors_config=fake_models.VectorParams.return_value,
        )

    def test_create_collection_wraps_failure(self):
        fake_models = MagicMock()
        self.client.create_collection.side_effect = RuntimeError("boom")
        with patch.dict(
            sys.modules,
            {
                "qdrant_client": MagicMock(),
                "qdrant_client.models": fake_models,
            },
        ):
            with self.assertRaises(VectorStoreError):
                self.provider.create_collection("memories", 8, "Cosine")

    # --- delete_collection ----------------------------------------------
    def test_delete_collection_delegates(self):
        self.provider.delete_collection("memories")
        self.client.delete_collection.assert_called_once_with("memories")

    def test_delete_collection_wraps_failure(self):
        self.client.delete_collection.side_effect = RuntimeError("boom")
        with self.assertRaises(VectorStoreError):
            self.provider.delete_collection("memories")

    # --- upsert_vector (Sprint 10.3, index write only) -------------------
    def test_upsert_vector_delegates_to_client(self):
        fake_models = MagicMock(name="qdrant_client.models")
        payload = {"memory_id": "m1", "employee_id": "e1"}
        with patch.dict(
            sys.modules,
            {
                "qdrant_client": MagicMock(name="qdrant_client"),
                "qdrant_client.models": fake_models,
            },
        ):
            self.provider.upsert_vector(
                "memories", "point-1", [0.1, 0.2, 0.3], payload
            )

        fake_models.PointStruct.assert_called_once_with(
            id="point-1", vector=[0.1, 0.2, 0.3], payload=payload
        )
        self.client.upsert.assert_called_once_with(
            collection_name="memories",
            points=[fake_models.PointStruct.return_value],
        )

    def test_upsert_vector_wraps_failure(self):
        fake_models = MagicMock()
        self.client.upsert.side_effect = RuntimeError("boom")
        with patch.dict(
            sys.modules,
            {
                "qdrant_client": MagicMock(),
                "qdrant_client.models": fake_models,
            },
        ):
            with self.assertRaises(VectorStoreError):
                self.provider.upsert_vector("memories", "p1", [0.1], {})

    # --- no search surface (Sprint 10.3 adds ONLY upsert) ----------------
    def test_provider_exposes_no_search_operations(self):
        # upsert_vector exists (indexing); search/query variants must not.
        self.assertTrue(hasattr(self.provider, "upsert_vector"))
        for forbidden in (
            "search",
            "query",
            "similarity_search",
            "nearest_neighbors",
            "hybrid_search",
            "delete_by_filter",
        ):
            self.assertFalse(
                hasattr(self.provider, forbidden),
                f"unexpected {forbidden!r} on QdrantProvider",
            )


# =====================================================================
# VectorStoreService (provider mocked)
# =====================================================================
class VectorStoreServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MagicMock(name="VectorStoreProvider")
        self.service = VectorStoreService(self.provider)

    def test_health_check_delegates_and_returns_unchanged(self):
        self.provider.health_check.return_value = True
        self.assertTrue(self.service.health_check())
        self.provider.health_check.assert_called_once_with()

    def test_collection_exists_delegates(self):
        self.provider.collection_exists.return_value = False
        self.assertFalse(self.service.collection_exists("memories"))
        self.provider.collection_exists.assert_called_once_with("memories")

    def test_create_collection_delegates_with_args(self):
        self.service.create_collection("memories", 1536, "Cosine")
        self.provider.create_collection.assert_called_once_with(
            "memories", 1536, "Cosine"
        )

    def test_create_collection_uses_default_distance(self):
        self.service.create_collection("memories", 1536)
        self.provider.create_collection.assert_called_once_with(
            "memories", 1536, "Cosine"
        )

    def test_delete_collection_delegates(self):
        self.service.delete_collection("memories")
        self.provider.delete_collection.assert_called_once_with("memories")

    def test_upsert_vector_delegates_with_args(self):
        payload = {"memory_id": "m1"}
        self.service.upsert_vector("memories", "p1", [0.1, 0.2], payload)
        self.provider.upsert_vector.assert_called_once_with(
            "memories", "p1", [0.1, 0.2], payload
        )

    def test_provider_exception_propagates(self):
        self.provider.health_check.side_effect = VectorStoreError("down")
        with self.assertRaises(VectorStoreError):
            self.service.health_check()

    def test_stateless_only_injected_provider(self):
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class VectorStoreDependencyTests(unittest.TestCase):
    def test_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_vector_store_service

        provider = MagicMock(name="VectorStoreProvider")
        service = get_vector_store_service(provider)
        self.assertIsInstance(service, VectorStoreService)
        self.assertIs(service.provider, provider)

    def test_provider_dependency_resolves_to_qdrant(self):
        # Constructs a QdrantProvider from settings without importing the SDK
        # or contacting a server (the client is built lazily).
        from app.core.dependencies import get_vector_store_provider

        provider = get_vector_store_provider()
        self.assertIsInstance(provider, QdrantProvider)
        self.assertEqual(provider.name, "qdrant")


if __name__ == "__main__":
    unittest.main()
