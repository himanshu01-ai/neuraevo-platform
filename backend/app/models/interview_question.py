"""SQLAlchemy ORM model for blueprint interview questions.

Storage only — no AI generation, interview execution, or answer collection.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.blueprint import Blueprint
    from app.models.interview_answer import InterviewAnswer
    from app.models.interview_session_question import InterviewSessionQuestion


class InterviewQuestion(Base):
    """A single interview question belonging to a blueprint."""

    __tablename__ = "interview_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("blueprints.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_order: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Each question belongs to exactly one blueprint.
    blueprint: Mapped["Blueprint"] = relationship(
        back_populates="interview_questions"
    )

    # Each question has at most one answer.
    answer: Mapped[Optional["InterviewAnswer"]] = relationship(
        back_populates="question",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # A question may be referenced by many session-progress rows.
    session_questions: Mapped[List["InterviewSessionQuestion"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<InterviewQuestion id={self.id} order={self.question_order} "
            f"blueprint_id={self.blueprint_id}>"
        )
