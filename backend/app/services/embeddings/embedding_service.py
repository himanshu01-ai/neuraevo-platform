"""Embedding Service (Sprint 10.1 — abstraction only).

Accepts text, delegates to an injected :class:`EmbeddingProvider`, and returns
the provider's embedding vector unchanged. That is its entire responsibility.

It performs NO caching, retries, batching, persistence, database or vector-DB
access, repository usage, logging, or embedding logic of its own. The provider
is injected via the constructor (never instantiated here). No concrete provider
exists yet — integration and actual embedding generation are later sprints.
"""

from typing import List

from app.services.embeddings.providers.base import EmbeddingProvider


class EmbeddingService:
    """Delegates embedding generation to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def generate_embedding(self, text: str) -> List[float]:
        """Return the provider's embedding vector for ``text``, unchanged.

        ``text`` is passed to the provider untouched and the returned vector is
        handed back to the caller as-is. Provider exceptions propagate
        unchanged.
        """
        return self.provider.generate_embedding(text)
