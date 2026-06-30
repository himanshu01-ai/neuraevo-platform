"""Interview aggregation for blueprint generation.

``BlueprintContextBuilder`` turns an employee, its blueprint, and the
interview question/answer pairs into a structured, AI-ready context. It is a
pure transformation: no database access, no AI calls, fully deterministic.
"""

from typing import Sequence

from app.models.blueprint import Blueprint
from app.models.employee import Employee
from app.schemas.blueprint_generation import (
    BlueprintFieldSet,
    BlueprintGenerationContext,
    InterviewQAItem,
)


def _is_answered(answer_text: str | None) -> bool:
    return answer_text is not None and answer_text.strip() != ""


class BlueprintContextBuilder:
    """Build a :class:`BlueprintGenerationContext` from interview data."""

    def build(
        self,
        *,
        employee: Employee,
        blueprint: Blueprint,
        qa_pairs: Sequence[tuple],
    ) -> BlueprintGenerationContext:
        """Assemble the generation context.

        ``qa_pairs`` is a sequence of ``(question, answer_text)`` tuples where
        ``question`` is an :class:`InterviewQuestion` and ``answer_text`` is an
        optional string. Items are emitted in the order provided (callers pass
        them ordered by ``question_order``).
        """
        qa_items: list[InterviewQAItem] = []
        for question, answer_text in qa_pairs:
            qa_items.append(
                InterviewQAItem(
                    question_id=question.id,
                    question_order=question.question_order,
                    question_text=question.question_text,
                    answer_text=answer_text,
                    answered=_is_answered(answer_text),
                )
            )

        total = len(qa_items)
        answered = sum(1 for item in qa_items if item.answered)
        completeness = (answered / total) if total else 0.0

        return BlueprintGenerationContext(
            employee_id=employee.id,
            blueprint_id=blueprint.id,
            employee_name=employee.name,
            role=employee.role,
            language=employee.language,
            personality=employee.personality,
            existing_blueprint=BlueprintFieldSet(
                vision=blueprint.vision,
                communication_style=blueprint.communication_style,
                personality_traits=blueprint.personality_traits,
                goals=blueprint.goals,
                constraints=blueprint.constraints,
                preferences=blueprint.preferences,
            ),
            qa_items=qa_items,
            total_questions=total,
            answered_count=answered,
            completeness=completeness,
        )
