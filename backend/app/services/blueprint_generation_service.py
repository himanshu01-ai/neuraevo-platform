"""Blueprint generation service (preview/foundation).

Orchestrates blueprint generation behind the service layer: validates
ownership (reusing :class:`BlueprintService`), aggregates interview data into a
context (:class:`BlueprintContextBuilder`), and runs the
:class:`BlueprintGenerator`. Sprint 4A is preview-only — it performs reads and
returns a draft, and never writes to the database.
"""

import uuid

from app.employee_builder.analyzer import BlueprintContextBuilder
from app.employee_builder.blueprint import BlueprintGenerator
from app.models.user import User
from app.repositories.interview_answer_repository import (
    InterviewAnswerRepository,
)
from app.repositories.interview_question_repository import (
    InterviewQuestionRepository,
)
from app.schemas.blueprint_generation import (
    BlueprintGenerationPreviewResponse,
    GenerationMetadata,
)
from app.services.blueprint_service import BlueprintService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlueprintGenerationService:
    """Coordinates a non-persisting blueprint generation preview.

    Read-only: it never commits. Ownership is enforced via
    :meth:`BlueprintService.get_blueprint`, which raises the employee/blueprint
    domain errors the API translates to 404/403.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.blueprints = BlueprintService(session)
        self.questions = InterviewQuestionRepository(session)
        self.answers = InterviewAnswerRepository(session)
        self.context_builder = BlueprintContextBuilder()
        self.generator = BlueprintGenerator()

    def preview_generation(
        self, owner: User, employee_id: uuid.UUID
    ) -> BlueprintGenerationPreviewResponse:
        """Build a generation preview for the employee's blueprint.

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` /
        ``BlueprintNotFoundError`` via the ownership chain. Performs no writes.
        """
        blueprint = self.blueprints.get_blueprint(owner, employee_id)
        employee = blueprint.employee

        # Aggregate interview Q&A (reads only), ordered by question_order.
        questions = self.questions.list_questions(blueprint.id)
        qa_pairs: list[tuple] = []
        for question in questions:
            answer = self.answers.get_answer(question.id)
            qa_pairs.append(
                (question, answer.answer_text if answer is not None else None)
            )

        context = self.context_builder.build(
            employee=employee, blueprint=blueprint, qa_pairs=qa_pairs
        )
        result = self.generator.generate(context)

        logger.info(
            "User %s previewed blueprint generation for employee %s "
            "(%d/%d answered, provider=%s)",
            owner.id,
            employee_id,
            context.answered_count,
            context.total_questions,
            result.provider,
        )

        return BlueprintGenerationPreviewResponse(
            employee_id=employee.id,
            blueprint_id=blueprint.id,
            context=context,
            prompt=result.prompt,
            draft=result.draft,
            metadata=GenerationMetadata(
                provider=result.provider,
                model=result.model,
                deterministic=result.deterministic,
                persisted=False,
            ),
            warnings=result.warnings,
        )
