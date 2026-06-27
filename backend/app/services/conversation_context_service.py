"""Conversation context service: assemble conversation history into context.

Read-only orchestration. Reuses :class:`ConversationService` for the
User -> Employee -> Conversation ownership chain and the message repository to
load history (oldest first), then assembles a reusable context structure. No
AI generation, prompts, or providers.
"""

import uuid

from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.schemas.conversation_context import (
    ConversationContextMessage,
    ConversationContextResponse,
)
from app.services.conversation_service import ConversationService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationContextService:
    """Builds a structured conversation-history context."""

    def __init__(self, session) -> None:
        self.session = session
        # Reused for the User -> Employee -> Conversation ownership chain.
        self.conversations = ConversationService(session)
        self.messages = MessageRepository(session)

    def build_context(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> ConversationContextResponse:
        """Assemble the conversation's message history into context.

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` /
        ``ConversationNotFoundError`` via the reused ownership chain. Messages
        are ordered oldest-first (matching Sprint 5B). An empty conversation
        yields ``message_count = 0`` and an empty list.
        """
        conversation = self.conversations.get_conversation(
            owner, employee_id, conversation_id
        )
        messages = self.messages.list_messages(conversation.id)

        context_messages = [
            ConversationContextMessage(role=m.role, content=m.content)
            for m in messages
        ]

        logger.info(
            "User %s built context for conversation %s (%d messages)",
            owner.id,
            conversation.id,
            len(context_messages),
        )
        return ConversationContextResponse(
            employee_id=conversation.employee_id,
            conversation_id=conversation.id,
            message_count=len(context_messages),
            messages=context_messages,
        )
