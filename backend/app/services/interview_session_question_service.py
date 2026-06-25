"""Interview session-question service: links questions into sessions.

Enforces ownership by reusing :class:`InterviewSessionService` (employee owns
session) and :class:`InterviewQuestionService` (employee owns question), then
manages the per-session question progress rows. Enforces the
one-question-per-session rule and status-transition rules. No AI, scoring, or
evaluation.
"""

import uuid
from typing import Optional, Sequence

from app.models.interview_session_question import InterviewSessionQuestion
from app.models.user import User
from app.repositories.interview_session_question_repository import (
    InterviewSessionQuestionRepository,
)
from app.schemas.interview_session_question import (
    SessionQuestionCreate,
    SessionQuestionUpdate,
)
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_session_service import InterviewSessionService
from app.utils.constants import SessionQuestionStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Permitted status transitions (including idempotent self-transitions).
_ALLOWED_TRANSITIONS: dict[SessionQuestionStatus, set[SessionQuestionStatus]] = {
    SessionQuestionStatus.PENDING: {
        SessionQuestionStatus.PENDING,
        SessionQuestionStatus.ANSWERED,
    },
    SessionQuestionStatus.ANSWERED: {SessionQuestionStatus.ANSWERED},
}


class InterviewSessionQuestionError(Exception):
    """Base class for session-question domain errors."""


class InterviewSessionQuestionNotFoundError(InterviewSessionQuestionError):
    """Raised when no session-question exists for the session."""


class InterviewSessionQuestionAlreadyExistsError(InterviewSessionQuestionError):
    """Raised when linking a question already present in the session."""


class InterviewSessionQuestionStateError(InterviewSessionQuestionError):
    """Raised when an invalid status transition is attempted."""


class InterviewSessionQuestionService:
    """Coordinates session-question operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.session_questions = InterviewSessionQuestionRepository(session)
        # Reused for the User -> Employee -> Session / Question chains.
        self.sessions = InterviewSessionService(session)
        self.questions = InterviewQuestionService(session)

    def create_session_question(
        self,
        owner: User,
        employee_id: uuid.UUID,
        session_id: uuid.UUID,
        data: SessionQuestionCreate,
    ) -> InterviewSessionQuestion:
        """Link a question into a session.

        Verifies the employee owns both the session and the question, then
        rejects duplicates (same session + question) with
        :class:`InterviewSessionQuestionAlreadyExistsError`.
        """
        interview_session = self.sessions.get_session(
            owner, employee_id, session_id
        )
        question = self.questions.get_question(
            owner, employee_id, data.question_id
        )

        existing = self.session_questions.get_by_session_and_question(
            interview_session.id, question.id
        )
        if existing is not None:
            raise InterviewSessionQuestionAlreadyExistsError(
                f"{session_id}:{data.question_id}"
            )

        session_question = self.session_questions.create_session_question(
            interview_session.id, question.id
        )
        self.session.commit()
        self.session.refresh(session_question)
        logger.info(
            "User %s linked question %s into session %s (sq=%s)",
            owner.id,
            question.id,
            interview_session.id,
            session_question.id,
        )
        return session_question

    def list_session_questions(
        self, owner: User, employee_id: uuid.UUID, session_id: uuid.UUID
    ) -> Sequence[InterviewSessionQuestion]:
        """List a session's question links, ordered by created_at."""
        interview_session = self.sessions.get_session(
            owner, employee_id, session_id
        )
        return self.session_questions.list_session_questions(
            interview_session.id
        )

    def get_session_question(
        self,
        owner: User,
        employee_id: uuid.UUID,
        session_id: uuid.UUID,
        session_question_id: uuid.UUID,
    ) -> InterviewSessionQuestion:
        """Return a single session-question scoped to the session.

        Raises :class:`InterviewSessionQuestionNotFoundError` if it does not
        exist or belongs to a different session.
        """
        interview_session = self.sessions.get_session(
            owner, employee_id, session_id
        )
        session_question = self.session_questions.get_session_question(
            session_question_id
        )
        if (
            session_question is None
            or session_question.session_id != interview_session.id
        ):
            raise InterviewSessionQuestionNotFoundError(str(session_question_id))
        return session_question

    def update_session_question(
        self,
        owner: User,
        employee_id: uuid.UUID,
        session_id: uuid.UUID,
        session_question_id: uuid.UUID,
        data: SessionQuestionUpdate,
    ) -> InterviewSessionQuestion:
        """Update a session-question status, enforcing valid transitions.

        Raises :class:`InterviewSessionQuestionStateError` for a disallowed
        transition.
        """
        session_question = self.get_session_question(
            owner, employee_id, session_id, session_question_id
        )

        new_status: Optional[str] = None
        if data.status is not None:
            current = SessionQuestionStatus(session_question.status)
            if data.status not in _ALLOWED_TRANSITIONS[current]:
                raise InterviewSessionQuestionStateError(
                    f"Cannot transition from {current.value} to {data.status.value}."
                )
            new_status = data.status.value

        self.session_questions.update_session_question(
            session_question, status=new_status
        )
        self.session.commit()
        self.session.refresh(session_question)
        logger.info(
            "User %s updated session-question %s (status=%s)",
            owner.id,
            session_question_id,
            session_question.status,
        )
        return session_question

    def delete_session_question(
        self,
        owner: User,
        employee_id: uuid.UUID,
        session_id: uuid.UUID,
        session_question_id: uuid.UUID,
    ) -> None:
        """Delete a session-question scoped to the session."""
        session_question = self.get_session_question(
            owner, employee_id, session_id, session_question_id
        )
        self.session_questions.delete_session_question(session_question)
        self.session.commit()
        logger.info(
            "User %s deleted session-question %s",
            owner.id,
            session_question_id,
        )
