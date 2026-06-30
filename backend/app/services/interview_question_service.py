"""Interview question service: create, list, retrieve, and delete questions.

Enforces the full ownership chain (User -> Employee -> Blueprint -> Question)
by reusing :class:`BlueprintService` to resolve and authorize the employee's
blueprint. No AI generation, interview execution, or answer collection.
"""

import uuid
from typing import Sequence

from app.models.interview_question import InterviewQuestion
from app.models.user import User
from app.repositories.interview_question_repository import (
    InterviewQuestionRepository,
)
from app.schemas.interview_question import InterviewQuestionCreate
from app.services.blueprint_service import BlueprintService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class InterviewQuestionError(Exception):
    """Base class for interview-question domain errors."""


class InterviewQuestionNotFoundError(InterviewQuestionError):
    """Raised when a question does not exist for the employee's blueprint."""


class InterviewQuestionService:
    """Coordinates interview-question operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service commits the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.questions = InterviewQuestionRepository(session)
        # Reused for the User -> Employee -> Blueprint ownership chain.
        self.blueprints = BlueprintService(session)

    def create_question(
        self,
        owner: User,
        employee_id: uuid.UUID,
        data: InterviewQuestionCreate,
    ) -> InterviewQuestion:
        """Create a question on the employee's blueprint."""
        blueprint = self.blueprints.get_blueprint(owner, employee_id)
        question = self.questions.create_question(blueprint.id, data)
        self.session.commit()
        self.session.refresh(question)
        logger.info(
            "User %s created interview question %s on blueprint %s",
            owner.id,
            question.id,
            blueprint.id,
        )
        return question

    def list_questions(
        self, owner: User, employee_id: uuid.UUID
    ) -> Sequence[InterviewQuestion]:
        """List the employee's blueprint questions, ordered by question_order."""
        blueprint = self.blueprints.get_blueprint(owner, employee_id)
        return self.questions.list_questions(blueprint.id)

    def get_question(
        self,
        owner: User,
        employee_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> InterviewQuestion:
        """Return a single question scoped to the employee's blueprint.

        Raises the employee/blueprint domain errors via the ownership chain,
        and :class:`InterviewQuestionNotFoundError` if the question does not
        exist or belongs to a different blueprint.
        """
        blueprint = self.blueprints.get_blueprint(owner, employee_id)
        question = self.questions.get_question(question_id)
        if question is None or question.blueprint_id != blueprint.id:
            raise InterviewQuestionNotFoundError(str(question_id))
        return question

    def delete_question(
        self,
        owner: User,
        employee_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> None:
        """Delete a question scoped to the employee's blueprint."""
        question = self.get_question(owner, employee_id, question_id)
        self.questions.delete_question(question)
        self.session.commit()
        logger.info(
            "User %s deleted interview question %s",
            owner.id,
            question_id,
        )
