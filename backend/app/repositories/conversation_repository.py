"""Data-access layer for :class:`~app.models.conversation.Conversation`.

Persistence only — no business logic, authorization, or validation.
Transaction control is left to the caller; methods ``flush`` so generated
values like ``id`` are populated.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.schemas.conversation import ConversationCreate


class ConversationRepository:
    """CRUD-style accessors for :class:`Conversation` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self, employee_id: uuid.UUID, data: ConversationCreate
    ) -> Conversation:
        """Persist a new conversation for ``employee_id`` (status defaults)."""
        conversation = Conversation(
            employee_id=employee_id,
            title=data.title,
        )
        self.session.add(conversation)
        self.session.flush()
        self.session.refresh(conversation)
        return conversation

    def get(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        return self.session.get(Conversation, conversation_id)

    def list_by_employee(
        self, employee_id: uuid.UUID
    ) -> Sequence[Conversation]:
        """Return an employee's conversations ordered by ``created_at``."""
        stmt = (
            select(Conversation)
            .where(Conversation.employee_id == employee_id)
            .order_by(Conversation.created_at)
        )
        return self.session.scalars(stmt).all()

    def update(
        self,
        conversation: Conversation,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Conversation:
        """Apply a partial update to an existing conversation instance.

        Only arguments that are not ``None`` are written; unspecified fields
        are left untouched. The instance is assumed to already be loaded and
        authorized by the caller.
        """
        if title is not None:
            conversation.title = title
        if status is not None:
            conversation.status = status
        self.session.flush()
        self.session.refresh(conversation)
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.session.delete(conversation)
        self.session.flush()
