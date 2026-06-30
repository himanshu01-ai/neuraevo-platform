"""Data-access layer for :class:`~app.models.interview_answer.InterviewAnswer`.

Persistence only — no business logic or authorization. Transaction control is
left to the caller; methods ``flush`` so generated values like ``id`` are
populated.
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview_answer import InterviewAnswer
from app.schemas.interview_answer import InterviewAnswerCreate


class InterviewAnswerRepository:
    """CRUD-style accessors for :class:`InterviewAnswer` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_answer(
        self, question_id: uuid.UUID, data: InterviewAnswerCreate
    ) -> InterviewAnswer:
        """Persist a new answer for ``question_id``."""
        answer = InterviewAnswer(
            question_id=question_id,
            answer_text=data.answer_text,
        )
        self.session.add(answer)
        self.session.flush()
        self.session.refresh(answer)
        return answer

    def get_answer(self, question_id: uuid.UUID) -> Optional[InterviewAnswer]:
        """Return the answer for ``question_id``, or ``None`` if absent."""
        stmt = select(InterviewAnswer).where(
            InterviewAnswer.question_id == question_id
        )
        return self.session.scalar(stmt)

    def update_answer(
        self,
        answer: InterviewAnswer,
        *,
        answer_text: Optional[str] = None,
    ) -> InterviewAnswer:
        """Apply a partial update to an existing ``answer`` instance.

        Only arguments that are not ``None`` are written; unspecified fields
        are left untouched. The ``answer`` is assumed to already be loaded and
        authorized by the caller.
        """
        if answer_text is not None:
            answer.answer_text = answer_text
        self.session.flush()
        self.session.refresh(answer)
        return answer

    def delete_answer(self, answer: InterviewAnswer) -> None:
        self.session.delete(answer)
        self.session.flush()
