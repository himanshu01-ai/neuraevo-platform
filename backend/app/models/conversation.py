"""SQLAlchemy ORM model for employee conversations.

A conversation is a container belonging to a single employee. Sprint 5A scope
is lifecycle only — no messages, AI, or memory. ``status`` is stored as a
plain string; allowed values are defined by
:class:`app.utils.constants.ConversationStatus` and validated at the schema
and service layers.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import ConversationStatus

if TYPE_CHECKING:
    from app.models.employee import Employee


class Conversation(Base):
    """A conversation container belonging to an employee."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=ConversationStatus.ACTIVE.value, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Each conversation belongs to exactly one employee.
    employee: Mapped["Employee"] = relationship(
        back_populates="conversations"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Conversation id={self.id} title={self.title!r} "
            f"status={self.status!r} employee_id={self.employee_id}>"
        )
