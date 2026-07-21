"""Conversation service: lifecycle management for employee conversations.

Owns ownership validation, transaction boundaries, and orchestration. Status
values are validated by the :class:`ConversationStatus` enum at the schema
layer; all transitions between ``active`` and ``archived`` are permitted, so no
transition rules are enforced here. No AI, messages, or memory logic.
"""

import uuid
from typing import Optional, Sequence, Tuple

from app.models.conversation import Conversation
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
    EmployeeService,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationError(Exception):
    """Base class for conversation domain errors."""


class ConversationNotFoundError(ConversationError):
    """Raised when no conversation exists for the employee."""


class ConversationService:
    """Coordinates conversation operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction. Ownership is enforced by reusing
    :class:`EmployeeService` (User -> Employee chain).
    """

    def __init__(self, session) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        # Reused for the User -> Employee ownership chain.
        self.employees = EmployeeService(session)

    def create_conversation(
        self, owner: User, employee_id: uuid.UUID, data: ConversationCreate
    ) -> Conversation:
        """Create a conversation for an employee the owner can access."""
        employee = self.employees.get_employee(owner, employee_id)
        conversation = self.conversations.create(employee.id, data)
        self.session.commit()
        self.session.refresh(conversation)
        logger.info(
            "User %s created conversation %s for employee %s",
            owner.id,
            conversation.id,
            employee.id,
        )
        return conversation

    def list_conversations(
        self, owner: User, employee_id: uuid.UUID
    ) -> Sequence[Conversation]:
        """List an employee's conversations, oldest first."""
        employee = self.employees.get_employee(owner, employee_id)
        return self.conversations.list_by_employee(employee.id)

    def get_conversation(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Conversation:
        """Return a single conversation scoped to the employee.

        Raises :class:`ConversationNotFoundError` if it does not exist or
        belongs to a different employee.
        """
        employee = self.employees.get_employee(owner, employee_id)
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation.employee_id != employee.id:
            raise ConversationNotFoundError(str(conversation_id))
        return conversation

    # --- User-scoped access (the platform interaction layer) -------------

    def get_for_user(
        self, owner: User, conversation_id: uuid.UUID
    ) -> Conversation:
        """Resolve a conversation by id for ``owner``, across any employee.

        Conversations are addressable by their own id here — the frontend holds
        a conversation id, not the employee behind it. Ownership is still the
        reused Employee chain: the conversation's employee must belong to
        ``owner``. A conversation that does not exist, or belongs to someone
        else, reads the same way — :class:`ConversationNotFoundError` — so this
        endpoint never reveals another user's conversations.
        """
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(str(conversation_id))
        try:
            self.employees.get_employee(owner, conversation.employee_id)
        except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
            raise ConversationNotFoundError(str(conversation_id)) from exc
        return conversation

    def list_for_user(
        self, owner: User
    ) -> Sequence[Tuple[Conversation, str, int, Optional[str]]]:
        """The owner's conversations across every employee, newest first.

        Each row is ``(Conversation, employee_name, message_count,
        last_message)`` — everything the sidebar needs — assembled in one query
        via the repository. Ownership is the join itself: only conversations
        whose employee belongs to ``owner`` are returned.
        """
        return self.conversations.list_summaries_for_user(owner.id)

    def overview_of(
        self, conversation: Conversation
    ) -> Tuple[str, int, Optional[str]]:
        """The owning employee's name, message count, and latest message.

        Takes an already-resolved conversation (ownership decided by whoever
        loaded it) and returns the display facts a single-conversation view
        needs, without re-deciding ownership.
        """
        return (
            conversation.employee.name,
            self.conversations.message_count(conversation.id),
            self.conversations.last_message_content(conversation.id),
        )

    def update_for_user(
        self, owner: User, conversation_id: uuid.UUID, data: ConversationUpdate
    ) -> Conversation:
        """Rename or archive/restore a conversation addressed by its id."""
        conversation = self.get_for_user(owner, conversation_id)
        self.conversations.update(
            conversation,
            title=data.title,
            status=data.status.value if data.status is not None else None,
        )
        self.session.commit()
        self.session.refresh(conversation)
        logger.info(
            "User %s updated conversation %s (status=%s)",
            owner.id,
            conversation_id,
            conversation.status,
        )
        return conversation

    def delete_for_user(
        self, owner: User, conversation_id: uuid.UUID
    ) -> None:
        """Delete a conversation addressed by its id."""
        conversation = self.get_for_user(owner, conversation_id)
        self.conversations.delete(conversation)
        self.session.commit()
        logger.info("User %s deleted conversation %s", owner.id, conversation_id)

    def update_conversation(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        data: ConversationUpdate,
    ) -> Conversation:
        """Apply a partial update (title and/or status) to a conversation."""
        conversation = self.get_conversation(
            owner, employee_id, conversation_id
        )
        self.conversations.update(
            conversation,
            title=data.title,
            status=data.status.value if data.status is not None else None,
        )
        self.session.commit()
        self.session.refresh(conversation)
        logger.info(
            "User %s updated conversation %s (status=%s)",
            owner.id,
            conversation_id,
            conversation.status,
        )
        return conversation

    def delete_conversation(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> None:
        """Delete a conversation scoped to the employee."""
        conversation = self.get_conversation(
            owner, employee_id, conversation_id
        )
        self.conversations.delete(conversation)
        self.session.commit()
        logger.info(
            "User %s deleted conversation %s",
            owner.id,
            conversation_id,
        )
