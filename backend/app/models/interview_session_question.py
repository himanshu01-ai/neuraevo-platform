"""SQLAlchemy ORM model linking interview sessions to interview questions.

Records which questions belong to a session and whether they have been
answered. Storage/execution foundation only — no AI, scoring, or evaluation.

``status`` is stored as a plain string; allowed values are defined by
:class:`app.utils.constants.SessionQuestionStatus` and validated at the schema
and service layers.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import SessionQuestionStatus

if TYPE_CHECKING:
    from app.models.interview_question import InterviewQuestion
    from app.models.interview_session import InterviewSession


class InterviewSessionQuestion(Base):
    """A question's membership and completion state within a session."""

    __tablename__ = "interview_session_questions"
    __table_args__ = (
        # A question can appear only once in a session.
        UniqueConstraint(
            "session_id", "question_id", name="uq_session_question"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), default=SessionQuestionStatus.PENDING.value, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["InterviewSession"] = relationship(
        back_populates="session_questions"
    )
    question: Mapped["InterviewQuestion"] = relationship(
        back_populates="session_questions"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<InterviewSessionQuestion id={self.id} status={self.status!r} "
            f"session_id={self.session_id} question_id={self.question_id}>"
        )
