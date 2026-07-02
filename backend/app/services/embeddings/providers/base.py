"""Embedding provider contract (Sprint 10.1 — abstraction only).

Defines the replaceable provider interface that future sprints will implement
(e.g. OpenAI / Voyage / Jina / Gemini / Cohere). This sprint ships ONLY the
abstraction: no concrete provider, no HTTP client, no SDK, no API key, no
embedding generation, and no vector database. Concrete providers — when added
later — will own all vendor-specific code behind this interface, isolated from
services, repositories, models, and routers.
"""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Replaceable strategy that turns text into an embedding vector.

    Concrete implementations (added in a later sprint) live behind this
    interface so the rest of the system stays provider-agnostic. This sprint
    provides only the abstract contract — there is no concrete provider yet.
    """

    name: str

    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Return the embedding vector for ``text``.

        Concrete implementations return the vector to the caller unchanged and
        perform no caching, batching, or retries here.
        """
