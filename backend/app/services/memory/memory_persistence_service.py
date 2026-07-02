"""Memory Persistence Service (Sprint 8.1; Sprint 10.3 adds vector indexing).

Write-only persistence of a completed conversation turn: after a successful AI
response, it stores the user message and the assistant message under the
existing conversation, in a single transaction. As of Sprint 10.3, once that
database write has committed, it also generates an embedding for the persisted
assistant memory and indexes it into the vector store — best-effort, after the
authoritative write.

PostgreSQL is always the source of truth; the vector store is only a searchable
index. Indexing runs strictly AFTER the DB commit and never rolls it back:

* DB write fails            -> no embedding, no indexing (nothing was saved).
* DB ok, embedding fails    -> record kept, no rollback, indexing skipped.
* DB ok, upsert fails       -> record kept, no rollback, memory stays persisted.

It performs NO retrieval, semantic search, ranking, similarity/query, importance
scoring, classification, ownership validation, or conversation modification.
Ownership is validated upstream. Collaborators are injected via the constructor.
"""

import uuid
from typing import Optional

from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.schemas.ai_response import AIResponse
from app.schemas.message import MessageCreate
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.utils.constants import MessageRole
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Vector-store collection that holds indexed conversation memories. This sprint
# only writes points into it; provisioning/creation is an operational concern.
_MEMORY_COLLECTION = "memories"


class MemoryPersistenceService:
    """Persists a completed turn, then best-effort indexes the saved memory.

    Collaborators are injected via the constructor (no repository, service, or
    provider is instantiated here): the request-scoped ``session`` (owns the
    transaction boundary), the reused Sprint 5B :class:`MessageRepository`
    (performs the writes), the Sprint 10.1 :class:`EmbeddingService`, and the
    Sprint 10.2 :class:`VectorStoreService` (index write). ``embeddings`` may be
    ``None`` while Sprint 10.1's provider seam is still unfulfilled, in which
    case indexing is simply skipped and persistence continues unchanged.
    """

    def __init__(
        self,
        session,
        messages: MessageRepository,
        embeddings: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStoreService] = None,
    ) -> None:
        self.session = session
        self.messages = messages
        self.embeddings = embeddings
        self.vector_store = vector_store

    def persist(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message: str,
        ai_response: AIResponse,
    ) -> None:
        """Store the turn, commit, then index the persisted assistant memory.

        Saves the user message then the assistant message (from
        ``ai_response.content``), both under ``conversation_id``, and commits
        atomically. Any persistence failure rolls back and propagates, leaving
        no partial write (and no embedding/indexing). Only after a successful
        commit is the assistant memory embedded and upserted into the vector
        store — a step that never rolls back and whose failures are swallowed so
        a saved memory is never lost to an indexing error. Returns nothing.
        """
        try:
            self.messages.create_message(
                conversation_id,
                MessageCreate(role=MessageRole.USER, content=user_message),
            )
            assistant_message = self.messages.create_message(
                conversation_id,
                MessageCreate(
                    role=MessageRole.ASSISTANT, content=ai_response.content
                ),
            )
            # Capture identity/content before commit (unaffected by
            # expire-on-commit); used only by the post-commit indexing step.
            memory_id = assistant_message.id
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        logger.info(
            "Persisted conversation turn for user %s employee %s "
            "conversation %s (user + assistant messages)",
            owner.id,
            employee_id,
            conversation_id,
        )

        # Best-effort indexing AFTER the authoritative DB commit. The database
        # record already exists and is never rolled back from here on.
        self._index_memory(
            owner,
            employee_id,
            conversation_id,
            memory_id,
            ai_response.content,
        )

    def _index_memory(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        memory_id: uuid.UUID,
        text: str,
    ) -> None:
        """Embed the saved memory and upsert it into the vector store.

        Runs only after a successful DB commit and never raises: if embedding
        or the vector upsert fails (or no embedding provider is wired yet), the
        failure is logged and the already-persisted memory is left intact. The
        vector-store point id is the PostgreSQL memory id, keeping Postgres the
        source of truth and the index keyed by the same identifier.
        """
        if self.embeddings is None or self.vector_store is None:
            # Provider not wired yet (Sprint 10.1 seam unfulfilled): indexing is
            # disabled; the persisted memory stands on its own.
            return

        try:
            vector = self.embeddings.generate_embedding(text)
        except Exception as exc:
            logger.warning(
                "Embedding generation failed; skipping vector index "
                "(memory %s stays persisted): %s",
                memory_id,
                exc,
            )
            return

        try:
            payload = {
                "memory_id": str(memory_id),
                "user_id": str(owner.id),
                "employee_id": str(employee_id),
                "conversation_id": str(conversation_id),
                "role": MessageRole.ASSISTANT.value,
                "content": text,
            }
            self.vector_store.upsert_vector(
                collection_name=_MEMORY_COLLECTION,
                point_id=str(memory_id),
                vector=vector,
                payload=payload,
            )
        except Exception as exc:
            logger.warning(
                "Vector upsert failed; memory %s stays persisted: %s",
                memory_id,
                exc,
            )
            return

        logger.info(
            "Indexed memory %s into vector store collection %s",
            memory_id,
            _MEMORY_COLLECTION,
        )
