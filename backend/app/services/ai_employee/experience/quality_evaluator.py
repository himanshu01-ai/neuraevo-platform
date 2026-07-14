"""Quality evaluator (Sprint 16.12 — evaluate task quality deterministically).

Defines :class:`QualityEvaluator`, which evaluates the quality of an observed task
into an immutable :class:`QualityAssessment` — reading whether the goal was achieved
and the output accepted, how many retries occurred, whether approval or recovery was
required, and a deterministic quality score. It also aggregates a set of tasks into a
single platform-level :class:`QualityAssessment`.

The score is a fixed, rule-based function of the observed signals (no AI, no LLM
evaluation, no learning). It reads only observed task state passed in or read from the
frozen Sprint 16.10 :class:`AIEmployeeService`; it observes only and executes,
delegates, and stores nothing, and it never modifies AI behaviour. Strictly additive
to Sprints 1.x–16.11, whose modules are left untouched.
"""

from typing import List, Optional

from app.services.ai_employee.experience import signals
from app.services.ai_employee.experience.models import QualityAssessment
from app.services.ai_employee.service import (
    AIEmployeeService,
    TaskStatusResponse,
)

# Deterministic score weights (a task starts at 100 and loses points per signal).
_MAX_SCORE = 100.0
_GOAL_PENALTY = 50.0
_OUTPUT_PENALTY = 20.0
_RETRY_PENALTY = 10.0
_RECOVERY_PENALTY = 15.0
_APPROVAL_PENALTY = 5.0

# The label a platform-level aggregate assessment carries in place of a task id.
_AGGREGATE_TASK_ID = "__platform__"


class QualityEvaluator:
    """Evaluates task quality into deterministic :class:`QualityAssessment` s.

    Constructed with an injected :class:`AIEmployeeService` (constructor injection; it
    instantiates none). ``evaluate`` scores a single observed task; ``evaluate_all``
    scores every observed task; and ``aggregate`` collapses a set into one
    platform-level assessment. The score is a fixed rule-based function of the observed
    signals — it is stateless, reads only, and runs nothing.
    """

    def __init__(self, service: AIEmployeeService) -> None:
        self.service = service

    def evaluate(self, task: TaskStatusResponse) -> QualityAssessment:
        """Return the deterministic :class:`QualityAssessment` for one observed task."""
        goal = signals.goal_achieved(task)
        output = signals.output_accepted(task)
        retries = signals.retry_count(task)
        approval = signals.approval_required(task)
        recovery = signals.recovery_required(task)
        return QualityAssessment(
            task_id=task.task_id,
            goal_achieved=goal,
            output_accepted=output,
            retry_count=retries,
            approval_required=approval,
            recovery_required=recovery,
            quality_score=self._score(
                goal, output, retries, approval, recovery
            ),
        )

    def evaluate_all(
        self, tasks: Optional[List[TaskStatusResponse]] = None
    ) -> List[QualityAssessment]:
        """Return a :class:`QualityAssessment` per observed task (order preserved)."""
        observed = signals.resolve_tasks(self.service, tasks)
        return [self.evaluate(task) for task in observed]

    def aggregate(
        self, tasks: Optional[List[TaskStatusResponse]] = None
    ) -> QualityAssessment:
        """Return one platform-level aggregate :class:`QualityAssessment`.

        ``goal_achieved`` / ``output_accepted`` hold only when every observed task
        does; ``retry_count`` sums retries; ``approval_required`` / ``recovery_required``
        hold when any task did; and ``quality_score`` is the mean per-task score
        (``0.0`` for an empty set). Deterministic; it runs nothing.
        """
        assessments = self.evaluate_all(tasks)
        count = len(assessments)
        if count == 0:
            return QualityAssessment(task_id=_AGGREGATE_TASK_ID)
        total_score = sum(a.quality_score for a in assessments)
        return QualityAssessment(
            task_id=_AGGREGATE_TASK_ID,
            goal_achieved=all(a.goal_achieved for a in assessments),
            output_accepted=all(a.output_accepted for a in assessments),
            retry_count=sum(a.retry_count for a in assessments),
            approval_required=any(a.approval_required for a in assessments),
            recovery_required=any(a.recovery_required for a in assessments),
            quality_score=round(total_score / count, 2),
            assessment_metadata={"task_count": count},
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _score(
        goal: bool,
        output: bool,
        retries: int,
        approval: bool,
        recovery: bool,
    ) -> float:
        """Return the deterministic quality score in ``[0, 100]`` for the signals."""
        score = _MAX_SCORE
        if not goal:
            score -= _GOAL_PENALTY
        if not output:
            score -= _OUTPUT_PENALTY
        score -= _RETRY_PENALTY * max(retries, 0)
        if recovery:
            score -= _RECOVERY_PENALTY
        if approval:
            score -= _APPROVAL_PENALTY
        return round(max(0.0, min(_MAX_SCORE, score)), 2)
