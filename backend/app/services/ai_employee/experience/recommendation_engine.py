"""Recommendation engine (Sprint 16.12 — deterministic, rule-based recommendations).

Defines :class:`RecommendationEngine`, which turns the platform's computed
:class:`ExperienceMetrics`, :class:`BehaviorMetrics`, :class:`FrictionReport`, and
aggregate :class:`QualityAssessment` into a deterministic list of immutable
:class:`ImprovementRecommendation` s — e.g. "improve browser capability", "reduce
workflow length", "optimize approval flow", "improve recovery".

Every recommendation is produced by a fixed rule against injected thresholds — there
is NO AI generation, no LLM, no prediction, and no learning. It reads only the DTOs it
is given; it observes only and executes, delegates, and stores nothing, and it never
modifies AI behaviour. Strictly additive to Sprints 1.x–16.11, whose modules are left
untouched.
"""

from typing import List

from app.services.ai_employee.experience.models import (
    BehaviorMetrics,
    ExperienceMetrics,
    FrictionReport,
    FrictionSeverity,
    FrictionType,
    ImprovementRecommendation,
    QualityAssessment,
    RecommendationCategory,
    RecommendationPriority,
)

# Deterministic ordering so recommendations sort high-priority-first, then by id.
_PRIORITY_ORDER = {
    RecommendationPriority.HIGH: 0,
    RecommendationPriority.MEDIUM: 1,
    RecommendationPriority.LOW: 2,
}

# Map a friction severity to the priority of the recommendation it drives.
_SEVERITY_PRIORITY = {
    FrictionSeverity.HIGH: RecommendationPriority.HIGH,
    FrictionSeverity.MEDIUM: RecommendationPriority.MEDIUM,
    FrictionSeverity.LOW: RecommendationPriority.LOW,
    FrictionSeverity.NONE: RecommendationPriority.LOW,
}


class RecommendationEngine:
    """Generates deterministic, rule-based improvement recommendations (no AI).

    Constructed with deterministic thresholds (constructor injection; it instantiates
    none). ``recommend`` applies a fixed set of rules to the computed metrics and
    friction/quality signals and returns the matching
    :class:`ImprovementRecommendation` s, ordered high-priority-first then by id. It is
    stateless, reads only, and runs nothing.
    """

    def __init__(
        self,
        capability_success_floor: float = 0.8,
        task_success_floor: float = 0.8,
        approval_ceiling: float = 0.5,
        recovery_ceiling: float = 0.3,
        quality_floor: float = 70.0,
    ) -> None:
        self.capability_success_floor = capability_success_floor
        self.task_success_floor = task_success_floor
        self.approval_ceiling = approval_ceiling
        self.recovery_ceiling = recovery_ceiling
        self.quality_floor = quality_floor

    def recommend(
        self,
        experience: ExperienceMetrics,
        behavior: BehaviorMetrics,
        friction: FrictionReport,
        quality: QualityAssessment,
    ) -> List[ImprovementRecommendation]:
        """Return the deterministic recommendations for the computed signals."""
        recommendations: List[ImprovementRecommendation] = []

        if experience.task_count > 0:
            recommendations.extend(self._capability_rules(experience))
            recommendations.extend(self._experience_rules(experience))
            recommendations.extend(self._quality_rules(quality))
        recommendations.extend(self._friction_rules(friction))

        # Assign deterministic ids in stable rule order, then order by priority.
        numbered = [
            recommendation.model_copy(
                update={"recommendation_id": f"rec-{index + 1}"}
            )
            for index, recommendation in enumerate(recommendations)
        ]
        numbered.sort(
            key=lambda rec: (
                _PRIORITY_ORDER[rec.priority],
                rec.recommendation_id,
            )
        )
        return numbered

    # --- rule groups -----------------------------------------------------
    def _capability_rules(
        self, experience: ExperienceMetrics
    ) -> List[ImprovementRecommendation]:
        """Recommend improving each capability below the success floor."""
        recommendations: List[ImprovementRecommendation] = []
        for name in sorted(experience.capability_success):
            rate = experience.capability_success[name]
            if rate >= self.capability_success_floor:
                continue
            priority = (
                RecommendationPriority.HIGH
                if rate < self.capability_success_floor / 2
                else RecommendationPriority.MEDIUM
            )
            recommendations.append(
                self._make(
                    RecommendationCategory.CAPABILITY,
                    priority,
                    f"Improve {name} capability",
                    f"The {name} capability succeeds only "
                    f"{round(rate * 100)}% of the time.",
                    f"capability_success[{name}]={rate} < "
                    f"{self.capability_success_floor}",
                    target=name,
                )
            )
        return recommendations

    def _experience_rules(
        self, experience: ExperienceMetrics
    ) -> List[ImprovementRecommendation]:
        """Recommend from the aggregate success, approval, and recovery rates."""
        recommendations: List[ImprovementRecommendation] = []
        if experience.task_success_rate < self.task_success_floor:
            recommendations.append(
                self._make(
                    RecommendationCategory.QUALITY,
                    RecommendationPriority.HIGH,
                    "Improve task reliability",
                    "Overall task success is below target.",
                    f"task_success_rate={experience.task_success_rate} < "
                    f"{self.task_success_floor}",
                    target="task_success",
                )
            )
        if experience.approval_rate > self.approval_ceiling:
            recommendations.append(
                self._make(
                    RecommendationCategory.APPROVAL,
                    RecommendationPriority.MEDIUM,
                    "Optimize approval flow",
                    "A large share of tasks require human approval.",
                    f"approval_rate={experience.approval_rate} > "
                    f"{self.approval_ceiling}",
                    target="approval_flow",
                )
            )
        if experience.recovery_rate > self.recovery_ceiling:
            recommendations.append(
                self._make(
                    RecommendationCategory.RECOVERY,
                    RecommendationPriority.MEDIUM,
                    "Improve recovery",
                    "A large share of tasks require recovery.",
                    f"recovery_rate={experience.recovery_rate} > "
                    f"{self.recovery_ceiling}",
                    target="recovery",
                )
            )
        return recommendations

    def _quality_rules(
        self, quality: QualityAssessment
    ) -> List[ImprovementRecommendation]:
        """Recommend improving output quality when the aggregate score is low."""
        if quality.quality_score >= self.quality_floor:
            return []
        return [
            self._make(
                RecommendationCategory.QUALITY,
                RecommendationPriority.MEDIUM,
                "Improve output quality",
                "The aggregate quality score is below target.",
                f"quality_score={quality.quality_score} < "
                f"{self.quality_floor}",
                target="output_quality",
            )
        ]

    def _friction_rules(
        self, friction: FrictionReport
    ) -> List[ImprovementRecommendation]:
        """Recommend one improvement per detected friction point."""
        recommendations: List[ImprovementRecommendation] = []
        for point in friction.points:
            recommendations.append(self._for_friction(point))
        return recommendations

    def _for_friction(self, point) -> ImprovementRecommendation:
        """Return the recommendation deterministically mapped from a friction point."""
        priority = _SEVERITY_PRIORITY[point.severity]
        mapping = {
            FrictionType.FREQUENT_FAILURES: (
                RecommendationCategory.QUALITY,
                "Investigate frequent failures",
                "reduce the task failure rate",
                "failures",
            ),
            FrictionType.REPEATED_RETRIES: (
                RecommendationCategory.RECOVERY,
                "Reduce repeated retries",
                "address the tasks that retry repeatedly",
                "retries",
            ),
            FrictionType.LONG_WORKFLOWS: (
                RecommendationCategory.WORKFLOW,
                "Reduce workflow length",
                "shorten long workflows",
                "workflow_length",
            ),
            FrictionType.ABANDONED_TASKS: (
                RecommendationCategory.EXPERIENCE,
                "Reduce abandoned tasks",
                "help users complete abandoned tasks",
                "abandonment",
            ),
            FrictionType.HIGH_CANCELLATION: (
                RecommendationCategory.EXPERIENCE,
                "Reduce cancellations",
                "lower the task cancellation rate",
                "cancellation",
            ),
        }
        category, title, action, target = mapping[point.friction_type]
        return self._make(
            category,
            priority,
            title,
            f"Detected {point.friction_type.value} friction; {action}.",
            point.detail,
            target=target,
        )

    # --- construction ----------------------------------------------------
    @staticmethod
    def _make(
        category: RecommendationCategory,
        priority: RecommendationPriority,
        title: str,
        detail: str,
        rationale: str,
        target: str = "",
    ) -> ImprovementRecommendation:
        """Build an :class:`ImprovementRecommendation` (id assigned by the caller)."""
        return ImprovementRecommendation(
            recommendation_id="rec-0",
            category=category,
            priority=priority,
            title=title,
            detail=detail,
            rationale=rationale,
            target=target,
        )
