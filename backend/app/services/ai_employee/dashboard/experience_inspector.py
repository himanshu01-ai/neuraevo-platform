"""Experience inspector (Sprint 16.14 — visualise experience intelligence).

Defines :class:`ExperienceInspector`, which projects the experience view of the
dashboard — feedback summary, quality metrics, friction reports, and recommendations —
by *reading* the frozen Sprint 16.12 :class:`ExperienceIntelligenceManager`. It never
executes a workflow, changes behaviour, or modifies state.

The experience platform already computes the feedback aggregates, aggregate quality
assessment, friction report, recommendations, and overall grade; the inspector reads
them into a deterministic :class:`ExperienceDashboard`. It observes only: it reads and
executes, delegates, and stores nothing. Strictly additive to Sprints 1.x–16.13, whose
modules are left untouched.
"""

from typing import Any, Dict, List

from app.services.ai_employee.dashboard.models import ExperienceDashboard


class ExperienceInspector:
    """Projects the experience dashboard from the experience platform (read-only).

    Constructed with an injected :class:`ExperienceIntelligenceManager` (constructor
    injection; it instantiates none). ``dashboard`` reads the feedback summary, aggregate
    quality, friction report, recommendations, and grade. It is stateless and reads only
    — it runs nothing.
    """

    def __init__(self, experience) -> None:
        self.experience = experience

    def dashboard(self) -> ExperienceDashboard:
        """Return the :class:`ExperienceDashboard` for the platform experience."""
        summary = self.experience.platform_summary()
        quality = self.experience.quality()
        friction = self.experience.friction()
        recommendations: List[Dict[str, Any]] = [
            {
                "recommendation_id": recommendation.recommendation_id,
                "category": recommendation.category.value,
                "priority": recommendation.priority.value,
                "title": recommendation.title,
            }
            for recommendation in self.experience.recommendations()
        ]
        quality_view: Dict[str, Any] = {
            "goal_achieved": quality.goal_achieved,
            "output_accepted": quality.output_accepted,
            "retry_count": quality.retry_count,
            "quality_score": quality.quality_score,
        }
        friction_view: Dict[str, Any] = {
            "friction_detected": friction.friction_detected,
            "points": len(friction.points),
            "highest_severity": friction.highest_severity.value,
        }
        return ExperienceDashboard(
            grade=summary.grade.value,
            feedback_summary=self.experience.feedback_summary(),
            quality=quality_view,
            friction=friction_view,
            recommendations=recommendations,
            dashboard_metadata={"source": "experience_intelligence"},
        )
