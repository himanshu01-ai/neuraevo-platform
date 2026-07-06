"""Plan explanation builder (Sprint 13.1 — human narration, no execution).

Turns an :class:`ExecutionPlan` into a single, plain-language sentence a person
can read to understand what the AI Employee intends to do — for example:

    "To plan your trip, I will first understand the destination, then review
    your calendar, ... and finally await your approval. I won't take any action
    until you approve the plan."

Explanation only: it reads the plan's data and produces text. It performs no
execution, provider, AI, or runtime work.
"""

from typing import List

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.models import ExecutionPlan


class PlanningExplanationBuilder:
    """Stateless renderer of a plan into a human-readable explanation.

    Holds no state and owns no session or provider. ``build`` narrates the
    ordered steps with ``first``/``then``/``finally`` connectors and appends the
    plan's confirmation intent and any open questions.
    """

    def build(self, plan: ExecutionPlan) -> str:
        """Return a plain-language explanation of ``plan`` (no execution).

        Narrates the steps in order, then notes that no action is taken until
        approval (when the plan requires confirmation) and what details are still
        needed (when ``missing_information`` is non-empty).
        """
        if not plan.steps:
            return f"I have no steps planned yet to {self._lower_first(plan.goal)}."

        phrases = [self._lower_first(step.description) for step in plan.steps]
        body = self._narrate(phrases)
        sentence = f"To {self._lower_first(plan.goal)}, {body}."

        if plan.requires_user_confirmation:
            sentence += " I won't take any action until you approve the plan."

        if plan.missing_information:
            needs = self._join(plan.missing_information)
            sentence += f" First, I'll need a few details from you: {needs}."

        return sentence

    def build_with_analysis(
        self, plan: ExecutionPlan, analysis: PlanAnalysis
    ) -> str:
        """Explain ``plan`` and fold in the ``analysis`` conclusions (no execution).

        Sprint 13.2 extension that reuses :meth:`build` for the step narration,
        then, per the analysis: prepends a clarification note when clarification
        is required, appends a confirmation note when confirmation is required,
        and appends a readiness note when the plan is ready. Explanation only —
        nothing is executed.
        """
        segments: List[str] = []
        if analysis.requires_clarification:
            segments.append(
                "I need a little more information before I can continue."
            )
        segments.append(self.build(plan))
        if analysis.requires_confirmation:
            segments.append(
                "I'll wait for your confirmation before executing."
            )
        if analysis.ready_for_execution:
            segments.append("The plan is ready for execution.")
        return " ".join(segments)

    @staticmethod
    def _narrate(phrases: List[str]) -> str:
        """Join step phrases with ``first``/``then``/``finally`` connectors."""
        if len(phrases) == 1:
            return f"I will {phrases[0]}"

        connectors = ["first"] + ["then"] * (len(phrases) - 2) + ["finally"]
        parts = [
            f"{connector} {phrase}"
            for connector, phrase in zip(connectors, phrases)
        ]
        return "I will " + ", ".join(parts[:-1]) + f", and {parts[-1]}"

    @staticmethod
    def _join(items: List[str]) -> str:
        """Join labels into a natural ``a``, ``b``, and ``c`` list."""
        cleaned = [item.strip() for item in items if item.strip()]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"

    @staticmethod
    def _lower_first(text: str) -> str:
        """Lower-case only the first character for mid-sentence readability."""
        stripped = text.strip()
        if not stripped:
            return stripped
        return stripped[0].lower() + stripped[1:]
