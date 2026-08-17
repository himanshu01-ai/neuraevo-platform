"""Improvement reporter (Sprint 16.12 — format deterministic improvement reports).

Defines :class:`ImprovementReporter`, which formats the platform's already-computed
metrics, friction, quality, and recommendations into immutable reports — a daily,
weekly, platform, or capability :class:`ImprovementReport`, and the platform-wide
:class:`PlatformExperienceSummary` with an overall :class:`ExperienceGrade`.

It is a pure formatter: it composes the DTOs it is given into report DTOs and decides,
computes rates, and executes nothing beyond deterministic assembly. There is no AI, no
prediction, no external dashboard, and no telemetry — it observes only. Strictly
additive to Sprints 1.x–16.11, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.experience.models import (
    BehaviorMetrics,
    ExperienceGrade,
    ExperienceMetrics,
    FrictionReport,
    FrictionSeverity,
    ImprovementRecommendation,
    ImprovementReport,
    PlatformExperienceSummary,
    QualityAssessment,
    ReportPeriod,
)


class ImprovementReporter:
    """Formats computed analysis into immutable reports (pure assembly, no execution).

    Stateless. ``daily_report`` / ``weekly_report`` / ``platform_report`` /
    ``capability_report`` assemble an :class:`ImprovementReport` for a chosen scope, and
    ``experience_summary`` assembles the :class:`PlatformExperienceSummary` with a
    deterministic :class:`ExperienceGrade`. It reads the DTOs it is given only — it runs
    nothing.
    """

    # --- period reports --------------------------------------------------
    def daily_report(
        self,
        experience: ExperienceMetrics,
        behavior: BehaviorMetrics,
        friction: FrictionReport,
        recommendations: Optional[List[ImprovementRecommendation]] = None,
        sequence: int = 0,
    ) -> ImprovementReport:
        """Assemble the daily :class:`ImprovementReport`."""
        return self._report(
            ReportPeriod.DAILY, experience, behavior, friction,
            recommendations, sequence,
        )

    def weekly_report(
        self,
        experience: ExperienceMetrics,
        behavior: BehaviorMetrics,
        friction: FrictionReport,
        recommendations: Optional[List[ImprovementRecommendation]] = None,
        sequence: int = 0,
    ) -> ImprovementReport:
        """Assemble the weekly :class:`ImprovementReport`."""
        return self._report(
            ReportPeriod.WEEKLY, experience, behavior, friction,
            recommendations, sequence,
        )

    def platform_report(
        self,
        experience: ExperienceMetrics,
        behavior: BehaviorMetrics,
        friction: FrictionReport,
        recommendations: Optional[List[ImprovementRecommendation]] = None,
        sequence: int = 0,
    ) -> ImprovementReport:
        """Assemble the full platform :class:`ImprovementReport`."""
        return self._report(
            ReportPeriod.PLATFORM, experience, behavior, friction,
            recommendations, sequence,
        )

    def capability_report(
        self,
        experience: ExperienceMetrics,
        recommendations: Optional[List[ImprovementRecommendation]] = None,
        sequence: int = 0,
    ) -> ImprovementReport:
        """Assemble a capability-focused :class:`ImprovementReport`.

        Highlights each observed capability's success fraction; ``behavior`` and
        ``friction`` are omitted from this scope.
        """
        highlights = [
            f"{name}: {round(rate * 100)}% success"
            for name, rate in sorted(experience.capability_success.items())
        ] or ["no capability activity observed"]
        capability_recs = [
            rec
            for rec in (recommendations or [])
            if rec.category.value == "CAPABILITY"
        ]
        return ImprovementReport(
            report_id="report-capability",
            period=ReportPeriod.CAPABILITY,
            generated_sequence=sequence,
            experience=experience,
            recommendations=capability_recs,
            highlights=highlights,
            report_metadata={
                "capabilities": len(experience.capability_success)
            },
        )

    # --- platform summary ------------------------------------------------
    def experience_summary(
        self,
        experience: ExperienceMetrics,
        behavior: BehaviorMetrics,
        friction: FrictionReport,
        quality: QualityAssessment,
        feedback_summary: Optional[Dict[str, Any]] = None,
        recommendation_count: int = 0,
    ) -> PlatformExperienceSummary:
        """Assemble the platform-wide :class:`PlatformExperienceSummary`."""
        summary = dict(feedback_summary or {})
        feedback_count = int(summary.get("count", 0))
        average_rating = float(summary.get("average_rating", 0.0))
        grade = self._grade(experience, quality, friction)
        return PlatformExperienceSummary(
            grade=grade,
            experience=experience,
            behavior=behavior,
            friction=friction,
            quality=quality,
            feedback_count=feedback_count,
            average_rating=average_rating,
            recommendation_count=recommendation_count,
            summary=(
                f"grade {grade.value}; "
                f"{experience.task_count} task(s); "
                f"success {experience.task_success_rate}; "
                f"{len(friction.points)} friction point(s)"
            ),
            summary_metadata={
                "highest_friction": friction.highest_severity.value
            },
        )

    # --- helpers ---------------------------------------------------------
    def _report(
        self,
        period: ReportPeriod,
        experience: ExperienceMetrics,
        behavior: BehaviorMetrics,
        friction: FrictionReport,
        recommendations: Optional[List[ImprovementRecommendation]],
        sequence: int,
    ) -> ImprovementReport:
        """Assemble an :class:`ImprovementReport` for ``period``."""
        recs = list(recommendations or [])
        return ImprovementReport(
            report_id=f"report-{period.value.lower()}",
            period=period,
            generated_sequence=sequence,
            experience=experience,
            behavior=behavior,
            friction=friction,
            recommendations=recs,
            highlights=self._highlights(experience, friction, recs),
            report_metadata={"recommendation_count": len(recs)},
        )

    @staticmethod
    def _highlights(
        experience: ExperienceMetrics,
        friction: FrictionReport,
        recommendations: List[ImprovementRecommendation],
    ) -> List[str]:
        """Return deterministic plain-text headline lines for a report."""
        return [
            f"{experience.task_count} task(s) observed",
            f"task success rate {experience.task_success_rate}",
            f"workflow completion rate "
            f"{experience.workflow_completion_rate}",
            f"{len(friction.points)} friction point(s)",
            f"{len(recommendations)} recommendation(s)",
        ]

    @staticmethod
    def _grade(
        experience: ExperienceMetrics,
        quality: QualityAssessment,
        friction: FrictionReport,
    ) -> ExperienceGrade:
        """Return the deterministic overall :class:`ExperienceGrade`.

        Blends the task success rate and the aggregate quality score, then caps the
        grade by the highest detected friction severity. An empty platform (no observed
        tasks) grades ``FAIR`` — neutral, not penalised.
        """
        if experience.task_count == 0:
            return ExperienceGrade.FAIR
        blended = (
            experience.task_success_rate + quality.quality_score / 100.0
        ) / 2.0
        if blended >= 0.9:
            grade = ExperienceGrade.EXCELLENT
        elif blended >= 0.75:
            grade = ExperienceGrade.GOOD
        elif blended >= 0.5:
            grade = ExperienceGrade.FAIR
        else:
            grade = ExperienceGrade.POOR
        # High friction caps at FAIR; medium friction caps at GOOD.
        if friction.highest_severity == FrictionSeverity.HIGH:
            grade = _min_grade(grade, ExperienceGrade.FAIR)
        elif friction.highest_severity == FrictionSeverity.MEDIUM:
            grade = _min_grade(grade, ExperienceGrade.GOOD)
        return grade


# Ordering so a friction cap can never raise a grade, only lower it.
_GRADE_ORDER = {
    ExperienceGrade.POOR: 0,
    ExperienceGrade.FAIR: 1,
    ExperienceGrade.GOOD: 2,
    ExperienceGrade.EXCELLENT: 3,
}


def _min_grade(
    grade: ExperienceGrade, cap: ExperienceGrade
) -> ExperienceGrade:
    """Return the lower of ``grade`` and ``cap`` in grade order."""
    return grade if _GRADE_ORDER[grade] <= _GRADE_ORDER[cap] else cap
