"""Data-access layer for :class:`~app.models.message.Message`.

Persistence only — no business logic, authorization, or AI. Transaction
control is left to the caller; ``create_message`` ``flush``es so generated
values like ``id`` are populated but does not commit.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message
from app.schemas.message import MessageCreate


class MessageRepository:
    """CRUD-style accessors for :class:`Message` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_message(
        self, conversation_id: uuid.UUID, data: MessageCreate
    ) -> Message:
        """Persist a new message for ``conversation_id``."""
        message = Message(
            conversation_id=conversation_id,
            role=data.role.value,
            content=data.content,
        )
        self.session.add(message)
        self.session.flush()
        self.session.refresh(message)
        return message

    def get_message(self, message_id: uuid.UUID) -> Optional[Message]:
        return self.session.get(Message, message_id)

    def list_messages(
        self, conversation_id: uuid.UUID
    ) -> Sequence[Message]:
        """Return a conversation's messages ordered by ``created_at`` (ASC)."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return self.session.scalars(stmt).all()

    def delete_message(self, message: Message) -> None:
        self.session.delete(message)
        self.session.flush()
