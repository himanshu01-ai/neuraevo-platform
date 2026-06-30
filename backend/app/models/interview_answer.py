"""SQLAlchemy ORM model for interview answers.

Storage only — no AI generation, blueprint generation, or interview execution.
Each interview question has at most one answer (enforced by a unique
constraint on ``question_id``).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.interview_question import InterviewQuestion


class InterviewAnswer(Base):
    """The single answer belonging to an interview question."""

    __tablename__ = "interview_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # One-to-one: each answer belongs to exactly one question.
    question: Mapped["InterviewQuestion"] = relationship(
        back_populates="answer"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<InterviewAnswer id={self.id} question_id={self.question_id}>"
