"""Unit tests for the Sprint 10.1 Embedding Service (abstraction only).

The provider is mocked, so no network, SDK, API key, or vector database is
touched. The tests verify that ``generate_embedding`` delegates to the injected
provider exactly once, passes the text through unchanged, returns the provider's
vector unchanged, propagates provider failures, and that the service is a
stateless, constructor-injected pass-through. Also covers the composition-root
wiring: the ``EmbeddingService`` DI provider resolves with an injected provider,
and the (intentionally unfulfilled) provider seam raises until a later sprint.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_embedding_service
"""

import unittest
from unittest.mock import MagicMock

from app.services.embeddings import EmbeddingProvider, EmbeddingService
from app.services.embeddings.providers.base import (
    EmbeddingProvider as BaseEmbeddingProvider,
)


class EmbeddingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = "Remember that the user prefers short replies."
        self.vector = [0.1, -0.2, 0.3, 0.4]
        self.provider = MagicMock(name="EmbeddingProvider")
        self.provider.generate_embedding.return_value = self.vector
        self.service = EmbeddingService(self.provider)

    def _generate(self):
        return self.service.generate_embedding(self.text)

    # --- delegation ------------------------------------------------------
    def test_delegates_to_provider(self):
        result = self._generate()
        self.assertEqual(result, self.vector)

    def test_provider_called_exactly_once(self):
        self._generate()
        self.provider.generate_embedding.assert_called_once()

    def test_text_passed_through_unchanged(self):
        self._generate()
        self.provider.generate_embedding.assert_called_once_with(self.text)

    # --- return value ----------------------------------------------------
    def test_returned_vector_unchanged(self):
        result = self._generate()
        self.assertIs(result, self.vector)

    # --- error propagation -----------------------------------------------
    def test_provider_exception_propagates(self):
        self.provider.generate_embedding.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self._generate()

    # --- statelessness / DI ----------------------------------------------
    def test_stateless_only_injected_provider(self):
        self.assertEqual(set(vars(self.service)), {"provider"})

    def test_constructor_uses_injected_provider(self):
        self.assertIs(self.service.provider, self.provider)

    # --- provider abstraction --------------------------------------------
    def test_provider_is_abstract_and_cannot_be_instantiated(self):
        self.assertIs(EmbeddingProvider, BaseEmbeddingProvider)
        with self.assertRaises(TypeError):
            EmbeddingProvider()  # abstract: generate_embedding not implemented

    # --- dependency injection provider -----------------------------------
    def test_di_service_provider_resolves_with_injected_provider(self):
        from app.core.dependencies import get_embedding_service

        service = get_embedding_service(self.provider)
        self.assertIsInstance(service, EmbeddingService)
        self.assertIs(service.provider, self.provider)

    def test_di_provider_seam_unfulfilled_until_later_sprint(self):
        # Sprint 10.1 ships only the abstraction: no concrete provider exists,
        # so the provider composition-root seam intentionally raises.
        from app.core.dependencies import get_embedding_provider

        with self.assertRaises(NotImplementedError):
            get_embedding_provider()


if __name__ == "__main__":
    unittest.main()
