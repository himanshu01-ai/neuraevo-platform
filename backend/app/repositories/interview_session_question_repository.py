"""Data-access layer for
:class:`~app.models.interview_session_question.InterviewSessionQuestion`.

Persistence only — no business logic, authorization, or state-transition
rules. Transaction control is left to the caller; methods ``flush`` so
generated values like ``id`` are populated.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview_session_question import InterviewSessionQuestion


class InterviewSessionQuestionRepository:
    """CRUD-style accessors for :class:`InterviewSessionQuestion` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_session_question(
        self, session_id: uuid.UUID, question_id: uuid.UUID
    ) -> InterviewSessionQuestion:
        """Persist a new session-question link (defaults to ``pending``)."""
        session_question = InterviewSessionQuestion(
            session_id=session_id,
            question_id=question_id,
        )
        self.session.add(session_question)
        self.session.flush()
        self.session.refresh(session_question)
        return session_question

    def get_session_question(
        self, session_question_id: uuid.UUID
    ) -> Optional[InterviewSessionQuestion]:
        return self.session.get(InterviewSessionQuestion, session_question_id)

    def get_by_session_and_question(
        self, session_id: uuid.UUID, question_id: uuid.UUID
    ) -> Optional[InterviewSessionQuestion]:
        """Return the link for a (session, question) pair, or ``None``."""
        stmt = select(InterviewSessionQuestion).where(
            InterviewSessionQuestion.session_id == session_id,
            InterviewSessionQuestion.question_id == question_id,
        )
        return self.session.scalar(stmt)

    def list_session_questions(
        self, session_id: uuid.UUID
    ) -> Sequence[InterviewSessionQuestion]:
        """Return a session's question links ordered by ``created_at``."""
        stmt = (
            select(InterviewSessionQuestion)
            .where(InterviewSessionQuestion.session_id == session_id)
            .order_by(InterviewSessionQuestion.created_at)
        )
        return self.session.scalars(stmt).all()

    def update_session_question(
        self,
        session_question: InterviewSessionQuestion,
        *,
        status: Optional[str] = None,
    ) -> InterviewSessionQuestion:
        """Apply a partial update to an existing session-question instance.

        Only arguments that are not ``None`` are written. The instance is
        assumed to already be loaded and authorized by the caller, and any
        state-transition validation done.
        """
        if status is not None:
            session_question.status = status
        self.session.flush()
        self.session.refresh(session_question)
        return session_question

    def delete_session_question(
        self, session_question: InterviewSessionQuestion
    ) -> None:
        self.session.delete(session_question)
        self.session.flush()
