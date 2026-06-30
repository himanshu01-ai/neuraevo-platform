"""Message service: lifecycle management for conversation messages.

Enforces the full ownership chain (User -> Employee -> Conversation -> Message)
by reusing :class:`ConversationService` to resolve and authorize the
conversation. Messages are immutable: there is no update/edit/regenerate
operation. No AI, generation, memory, or processing.
"""

import uuid
from typing import Sequence

from app.models.message import Message
from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate
from app.services.conversation_service import ConversationService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MessageError(Exception):
    """Base class for message domain errors."""


class MessageNotFoundError(MessageError):
    """Raised when a message does not exist for the conversation."""


class MessageService:
    """Coordinates message operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction. Ownership is enforced by reusing
    :class:`ConversationService` (User -> Employee -> Conversation chain).
    """

    def __init__(self, session) -> None:
        self.session = session
        self.messages = MessageRepository(session)
        # Reused for the User -> Employee -> Conversation ownership chain.
        self.conversations = ConversationService(session)

    def create_message(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        data: MessageCreate,
    ) -> Message:
        """Create a message in a conversation the owner can access."""
        conversation = self.conversations.get_conversation(
            owner, employee_id, conversation_id
        )
        message = self.messages.create_message(conversation.id, data)
        self.session.commit()
        self.session.refresh(message)
        logger.info(
            "User %s added %s message %s to conversation %s",
            owner.id,
            message.role,
            message.id,
            conversation.id,
        )
        return message

    def list_messages(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Sequence[Message]:
        """List a conversation's messages, oldest first."""
        conversation = self.conversations.get_conversation(
            owner, employee_id, conversation_id
        )
        return self.messages.list_messages(conversation.id)

    def get_message(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> Message:
        """Return a single message scoped to the conversation.

        Raises :class:`MessageNotFoundError` if it does not exist or belongs to
        a different conversation.
        """
        conversation = self.conversations.get_conversation(
            owner, employee_id, conversation_id
        )
        message = self.messages.get_message(message_id)
        if message is None or message.conversation_id != conversation.id:
            raise MessageNotFoundError(str(message_id))
        return message

    def delete_message(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> None:
        """Delete a message scoped to the conversation."""
        message = self.get_message(
            owner, employee_id, conversation_id, message_id
        )
        self.messages.delete_message(message)
        self.session.commit()
        logger.info(
            "User %s deleted message %s",
            owner.id,
            message_id,
        )
