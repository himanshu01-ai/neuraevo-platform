"""SQLAlchemy ORM model for conversation messages.

A message is an immutable entry in a conversation's chronological history.
Sprint 5B scope is persistence only — no AI, generation, or processing.
``role`` is stored as a plain string; allowed values are defined by
:class:`app.utils.constants.MessageRole` and validated at the schema layer.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base):
    """An immutable message belonging to a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Each message belongs to exactly one conversation.
    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Message id={self.id} role={self.role!r} "
            f"conversation_id={self.conversation_id}>"
        )
