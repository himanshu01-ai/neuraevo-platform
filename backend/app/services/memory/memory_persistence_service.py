"""Memory Persistence Service (Sprint 8.1).

Write-only persistence of a completed conversation turn: after a successful AI
response, it stores the user message and the assistant message under the
existing conversation, in a single transaction. That is its entire
responsibility.

It performs NO memory retrieval, semantic search, embeddings, importance
scoring, classification, AI/prompt/provider logic, ownership validation, or
conversation creation/modification. Ownership is already validated upstream in
the runtime pipeline before this service is ever called. It is not yet wired
into any flow or endpoint — integration is Sprint 8.2.
"""

import uuid

from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.schemas.ai_response import AIResponse
from app.schemas.message import MessageCreate
from app.utils.constants import MessageRole
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryPersistenceService:
    """Persists the user and assistant messages of a completed turn.

    Collaborators are injected via the constructor (no repository is
    instantiated here): the request-scoped ``session`` (owns the transaction
    boundary) and the reused Sprint 5B :class:`MessageRepository` (performs the
    writes). The service owns only the transaction — no ownership or business
    logic.
    """

    def __init__(self, session, messages: MessageRepository) -> None:
        self.session = session
        self.messages = messages

    def persist(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message: str,
        ai_response: AIResponse,
    ) -> None:
        """Store the user and assistant messages for one conversation turn.

        Saves the user message first, then the assistant message (from
        ``ai_response.content``), both associated with the existing
        ``conversation_id``, and commits atomically. Any persistence failure
        rolls back and propagates, leaving no partial write. Returns nothing.
        """
        try:
            self.messages.create_message(
                conversation_id,
                MessageCreate(role=MessageRole.USER, content=user_message),
            )
            self.messages.create_message(
                conversation_id,
                MessageCreate(
                    role=MessageRole.ASSISTANT, content=ai_response.content
                ),
            )
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
