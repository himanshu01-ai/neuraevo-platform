"""Memory Retrieval Service (Sprint 9.1; Sprint 10.4 adds semantic retrieval).

Read-only retrieval. It has two responsibilities:

* ``retrieve`` (Sprint 9.1) — return a conversation's messages, oldest first,
  from the Sprint 5B :class:`MessageRepository`, unchanged.
* ``retrieve_semantic`` (Sprint 10.4) — embed the current user query, ask the
  vector store for the most similar memory ids, then load the real memories
  from PostgreSQL (the source of truth) preserving the vector-search ranking.

PostgreSQL is authoritative: the vector store returns only ``(id, score)`` pairs
and its payload text is never trusted or returned. This service performs NO
prompt generation, hybrid/keyword search, reranking, metadata filtering,
summarization, compression, or prompt injection — those belong to later sprints.
Ownership is validated upstream before this service is called. Collaborators are
injected via the constructor (never instantiated here) and the service owns no
transaction and performs no writes.
"""

import uuid
from typing import List, Optional, Sequence

from app.models.message import Message
from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Vector-store collection holding indexed memories (written by Sprint 10.3).
_MEMORY_COLLECTION = "memories"
# Default number of semantically-ranked memories to return.
_DEFAULT_SEMANTIC_LIMIT = 10


class MemoryRetrievalService:
    """Retrieves conversation messages and semantically-ranked memories.

    The reused Sprint 5B :class:`MessageRepository` is injected via the
    constructor (never instantiated here). Sprint 10.4 also injects the Sprint
    10.1 :class:`EmbeddingService` and the Sprint 10.2 :class:`VectorStoreService`
    for semantic retrieval; ``embeddings`` may be ``None`` while Sprint 10.1's
    provider seam is still unfulfilled (in which case only the conversation-
    history ``retrieve`` is usable). The service holds no session and no other
    state — it performs no writes and owns no transaction.
    """

    def __init__(
        self,
        messages: MessageRepository,
        embeddings: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStoreService] = None,
    ) -> None:
        self.messages = messages
        self.embeddings = embeddings
        self.vector_store = vector_store

    def retrieve(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Sequence[Message]:
        """Return a conversation's messages, unchanged, oldest first.

        Ownership of ``conversation_id`` is assumed to already be validated
        upstream; this method performs no authorization checks, filtering,
        ranking, or other transformation of its own.
        """
        messages = self.messages.list_messages(conversation_id)
        logger.info(
            "Retrieved %d message(s) for user %s employee %s conversation %s",
            len(messages),
            owner.id,
            employee_id,
            conversation_id,
        )
        return messages

    def retrieve_semantic(
        self,
        query: str,
        limit: int = _DEFAULT_SEMANTIC_LIMIT,
    ) -> Sequence[Message]:
        """Return memories most semantically similar to ``query``.

        Flow: embed ``query`` -> similarity-search the vector store for the top
        ``limit`` memory ids (ordered by similarity) -> load those memories from
        PostgreSQL -> return them in the exact vector-search order.

        The vector store is only an index: its ``(id, score)`` results are used
        solely to pick and order ids; the returned rows (and their text) come
        entirely from PostgreSQL. An empty search returns ``[]``; ids with no
        PostgreSQL row are skipped. Embedding/vector-store failures propagate.
        """
        if self.embeddings is None or self.vector_store is None:
            raise RuntimeError(
                "Semantic retrieval requires an embedding service and a vector "
                "store; neither is wired until the embedding provider exists."
            )

        query_vector = self.embeddings.generate_embedding(query)
        ranked = self.vector_store.search_vectors(
            _MEMORY_COLLECTION, query_vector, limit
        )
        if not ranked:
            logger.info("Semantic retrieval for query returned 0 candidates")
            return []

        # Preserve the vector-search order; load the authoritative rows by id.
        ranked_ids = [uuid.UUID(str(point_id)) for point_id, _ in ranked]
        rows = self.messages.get_by_ids(ranked_ids)
        by_id = {row.id: row for row in rows}
        ordered: List[Message] = [
            by_id[memory_id] for memory_id in ranked_ids if memory_id in by_id
        ]

        logger.info(
            "Semantic retrieval matched %d candidate(s); loaded %d memory(ies) "
            "from PostgreSQL (ranking preserved)",
            len(ranked_ids),
            len(ordered),
        )
        return ordered
