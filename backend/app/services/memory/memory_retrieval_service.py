"""Memory Retrieval Service (Sprint 9.1).

Read-only retrieval of a conversation's existing messages: it asks the
existing Sprint 5B :class:`MessageRepository` for all messages belonging to a
conversation and returns them unchanged. That is its entire responsibility.

It performs NO prompt generation, ranking, summarization, filtering,
embeddings, vector/semantic search, context trimming, importance scoring,
provider calls, message mutation, or transaction commits. Ownership is
already validated upstream in the calling flow before this service is ever
called. It is not yet wired into any flow or endpoint — integration is a
later sprint.
"""

import uuid
from typing import Sequence

from app.models.message import Message
from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryRetrievalService:
    """Retrieves a conversation's messages via the existing repository.

    The reused Sprint 5B :class:`MessageRepository` is injected via the
    constructor (never instantiated here). The service holds no session and
    no other state — it performs no writes and owns no transaction.
    """

    def __init__(self, messages: MessageRepository) -> None:
        self.messages = messages

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
