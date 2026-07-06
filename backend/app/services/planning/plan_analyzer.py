"""Plan analyzer (Sprint 13.2 — deterministic ExecutionPlan analysis).

Reasoning-only component that inspects an :class:`ExecutionPlan` and produces a
:class:`PlanAnalysis`. Fully deterministic and offline: no AI, network, SDK,
runtime, tool, memory, or persistence involvement — the same plan in always
yields the same analysis out.

Its responsibilities are ONLY: analyse a plan and produce an analysis. It
executes nothing and mutates neither the plan nor any external state.
"""

from typing import List

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.models import ExecutionPlan

# Deterministic confidence penalties (documented, AI-free).
_MISSING_INFO_PENALTY = 0.2
_CONFIRMATION_PENALTY = 0.1


class PlanAnalyzer:
    """Stateless analyser: :class:`ExecutionPlan` -> :class:`PlanAnalysis`.

    Holds no state and owns no session, provider, or cache. It applies fixed
    rules: a plan is ready only when nothing is missing; each missing item yields
    one clarification question; confirmation intent is carried straight from the
    plan; and the risk summary and confidence are derived deterministically. It
    never executes a step.
    """

    def analyze(self, plan: ExecutionPlan) -> PlanAnalysis:
        """Return a deterministic :class:`PlanAnalysis` for ``plan`` (no execution).

        ``ready_for_execution`` is True exactly when the plan has no missing
        information. Missing items become clarification questions (so
        ``requires_clarification`` follows from them), while
        ``requires_confirmation`` mirrors the plan's own confirmation intent. The
        plan is only read — never mutated.
        """
        missing = list(plan.missing_information)
        clarification_questions = self._clarification_questions(missing)

        ready_for_execution = not missing
        requires_confirmation = plan.requires_user_confirmation
        requires_clarification = bool(clarification_questions)

        return PlanAnalysis(
            ready_for_execution=ready_for_execution,
            requires_confirmation=requires_confirmation,
            requires_clarification=requires_clarification,
            missing_information=missing,
            clarification_questions=clarification_questions,
            risk_summary=self._risk_summary(
                ready_for_execution, requires_confirmation, missing
            ),
            confidence=self._confidence(missing, requires_confirmation),
        )

    @staticmethod
    def _clarification_questions(missing: List[str]) -> List[str]:
        """One deterministic question per missing item, order preserved."""
        return [f"Could you tell me {item}?" for item in missing]

    @staticmethod
    def _risk_summary(
        ready: bool, requires_confirmation: bool, missing: List[str]
    ) -> str:
        """Deterministic, AI-free risk note derived from the plan's state."""
        if not ready:
            count = len(missing)
            noun = "detail" if count == 1 else "details"
            return (
                f"Not ready: {count} required {noun} missing; clarify before "
                "execution."
            )
        if requires_confirmation:
            return (
                "Plan is complete but requires user confirmation before "
                "execution."
            )
        return "Plan is ready for execution with no outstanding risks."

    @staticmethod
    def _confidence(missing: List[str], requires_confirmation: bool) -> float:
        """Deterministic ``0.0``–``1.0`` score penalising gaps and confirmation."""
        score = 1.0 - _MISSING_INFO_PENALTY * len(missing)
        if requires_confirmation:
            score -= _CONFIRMATION_PENALTY
        return round(max(0.0, min(1.0, score)), 2)
