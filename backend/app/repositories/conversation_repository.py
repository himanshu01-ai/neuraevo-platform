"""Data-access layer for :class:`~app.models.conversation.Conversation`.

Persistence only — no business logic, authorization, or validation.
Transaction control is left to the caller; methods ``flush`` so generated
values like ``id`` are populated.
"""

import uuid
from typing import Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.employee import Employee
from app.models.message import Message
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

    def list_summaries_for_user(
        self, user_id: uuid.UUID
    ) -> Sequence[Tuple[Conversation, str, int, Optional[str]]]:
        """The user's conversations across every employee, newest first.

        Joins ``conversations`` to ``employees`` and filters by owner, so a
        conversation is addressable without naming its employee first — the
        platform interaction layer's read. Each row carries the owning
        employee's name, the message count, and the latest message's content,
        computed with correlated subqueries so there is no per-conversation
        follow-up query. Soft-deleted employees' conversations are excluded.
        Returns ``(Conversation, employee_name, message_count, last_message)``.
        """
        message_count = (
            select(func.count(Message.id))
            .where(Message.conversation_id == Conversation.id)
            .scalar_subquery()
        )
        last_message = (
            select(Message.content)
            .where(Message.conversation_id == Conversation.id)
            .order_by(Message.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            select(Conversation, Employee.name, message_count, last_message)
            .join(Employee, Employee.id == Conversation.employee_id)
            .where(Employee.user_id == user_id, Employee.deleted_at.is_(None))
            .order_by(Conversation.updated_at.desc())
        )
        return [
            (row[0], row[1], int(row[2] or 0), row[3])
            for row in self.session.execute(stmt).all()
        ]

    def message_count(self, conversation_id: uuid.UUID) -> int:
        """How many messages a conversation holds."""
        stmt = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id
        )
        return int(self.session.scalar(stmt) or 0)

    def last_message_content(
        self, conversation_id: uuid.UUID
    ) -> Optional[str]:
        """The most recent message's content, or ``None`` for an empty thread."""
        stmt = (
            select(Message.content)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

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
