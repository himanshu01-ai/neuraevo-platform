"""Data-access layer for :class:`~app.models.interview_question.InterviewQuestion`.

Persistence only — no business logic or authorization. Transaction control is
left to the caller; methods ``flush`` so generated values like ``id`` are
populated.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview_question import InterviewQuestion
from app.schemas.interview_question import InterviewQuestionCreate


class InterviewQuestionRepository:
    """CRUD-style accessors for :class:`InterviewQuestion` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_question(
        self, blueprint_id: uuid.UUID, data: InterviewQuestionCreate
    ) -> InterviewQuestion:
        """Persist a new question for ``blueprint_id``."""
        question = InterviewQuestion(
            blueprint_id=blueprint_id,
            question_text=data.question_text,
            question_order=data.question_order,
        )
        self.session.add(question)
        self.session.flush()
        self.session.refresh(question)
        return question

    def get_question(
        self, question_id: uuid.UUID
    ) -> Optional[InterviewQuestion]:
        return self.session.get(InterviewQuestion, question_id)

    def list_questions(
        self, blueprint_id: uuid.UUID
    ) -> Sequence[InterviewQuestion]:
        """Return a blueprint's questions ordered by ``question_order``."""
        stmt = (
            select(InterviewQuestion)
            .where(InterviewQuestion.blueprint_id == blueprint_id)
            .order_by(InterviewQuestion.question_order)
        )
        return self.session.scalars(stmt).all()

    def delete_question(self, question: InterviewQuestion) -> None:
        self.session.delete(question)
        self.session.flush()
