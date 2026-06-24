"""Interview answer service: create, retrieve, update, and delete answers.

Enforces the full ownership chain (User -> Employee -> Blueprint -> Question ->
Answer) by reusing :class:`InterviewQuestionService` to resolve and authorize
the question. Enforces the one-answer-per-question rule. No AI, blueprint
generation, or interview execution.
"""

import uuid

from app.models.interview_answer import InterviewAnswer
from app.models.user import User
from app.repositories.interview_answer_repository import (
    InterviewAnswerRepository,
)
from app.schemas.interview_answer import (
    InterviewAnswerCreate,
    InterviewAnswerUpdate,
)
from app.services.interview_question_service import InterviewQuestionService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class InterviewAnswerError(Exception):
    """Base class for interview-answer domain errors."""


class InterviewAnswerNotFoundError(InterviewAnswerError):
    """Raised when a question has no answer."""


class InterviewAnswerAlreadyExistsError(InterviewAnswerError):
    """Raised when creating an answer for a question that already has one."""


class InterviewAnswerService:
    """Coordinates interview-answer operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.answers = InterviewAnswerRepository(session)
        # Reused for the User -> Employee -> Blueprint -> Question chain.
        self.questions = InterviewQuestionService(session)

    def create_answer(
        self,
        owner: User,
        employee_id: uuid.UUID,
        question_id: uuid.UUID,
        data: InterviewAnswerCreate,
    ) -> InterviewAnswer:
        """Create the answer for a question the owner can access.

        Raises the employee/blueprint/question domain errors via the ownership
        chain, and :class:`InterviewAnswerAlreadyExistsError` if the question
        already has an answer (one-per-question rule).
        """
        question = self.questions.get_question(owner, employee_id, question_id)
        if self.answers.get_answer(question.id) is not None:
            raise InterviewAnswerAlreadyExistsError(str(question_id))

        answer = self.answers.create_answer(question.id, data)
        self.session.commit()
        self.session.refresh(answer)
        logger.info(
            "User %s created answer %s for question %s",
            owner.id,
            answer.id,
            question.id,
        )
        return answer

    def get_answer(
        self, owner: User, employee_id: uuid.UUID, question_id: uuid.UUID
    ) -> InterviewAnswer:
        """Return the answer for a question the owner can access.

        Raises :class:`InterviewAnswerNotFoundError` if the question has none.
        """
        question = self.questions.get_question(owner, employee_id, question_id)
        answer = self.answers.get_answer(question.id)
        if answer is None:
            raise InterviewAnswerNotFoundError(str(question_id))
        return answer

    def update_answer(
        self,
        owner: User,
        employee_id: uuid.UUID,
        question_id: uuid.UUID,
        data: InterviewAnswerUpdate,
    ) -> InterviewAnswer:
        """Apply a partial update to a question's answer.

        Resolves and authorizes via :meth:`get_answer` (raising the same
        domain exceptions). Only fields set on ``data`` are written.
        """
        answer = self.get_answer(owner, employee_id, question_id)
        self.answers.update_answer(answer, answer_text=data.answer_text)
        self.session.commit()
        self.session.refresh(answer)
        logger.info(
            "User %s updated answer %s for question %s",
            owner.id,
            answer.id,
            question_id,
        )
        return answer

    def delete_answer(
        self, owner: User, employee_id: uuid.UUID, question_id: uuid.UUID
    ) -> None:
        """Delete a question's answer."""
        answer = self.get_answer(owner, employee_id, question_id)
        self.answers.delete_answer(answer)
        self.session.commit()
        logger.info(
            "User %s deleted answer for question %s",
            owner.id,
            question_id,
        )
