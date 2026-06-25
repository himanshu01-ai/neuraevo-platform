"""SQLAlchemy ORM model for interview sessions.

An interview session represents one interview run for an employee. Storage
only — no AI generation, scoring, evaluation, or report logic.

``status`` is stored as a plain string; allowed values are defined by
:class:`app.utils.constants.SessionStatus` and validated at the schema and
service layers.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import SessionStatus

if TYPE_CHECKING:
    from app.models.employee import Employee


class InterviewSession(Base):
    """A single interview run belonging to an employee."""

    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), default=SessionStatus.CREATED.value, nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Each session belongs to exactly one employee.
    employee: Mapped["Employee"] = relationship(
        back_populates="interview_sessions"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<InterviewSession id={self.id} status={self.status!r} "
            f"employee_id={self.employee_id}>"
        )
