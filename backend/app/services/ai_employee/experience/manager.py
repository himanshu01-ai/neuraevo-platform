"""Experience Intelligence manager (Sprint 16.12 — coordinate experience intelligence).

Defines :class:`ExperienceIntelligenceManager`, the coordinator of the Experience
Intelligence & Continuous Improvement Platform. It coordinates the platform's
observational surface over its injected collaborators — the :class:`FeedbackManager`,
:class:`ExperienceAnalyzer`, :class:`BehaviorAnalyzer`, :class:`QualityEvaluator`,
:class:`FrictionDetector`, :class:`RecommendationEngine`, and
:class:`ImprovementReporter` — and *delegates every business request to the frozen
Sprint 16.10* :class:`AIEmployeeService`:

    record_feedback    (collect one structured feedback record)
    analyze            (compute the full platform experience snapshot)
    recommendations    (deterministic, rule-based improvement recommendations)
    report             (assemble a scoped improvement report)
    platform_summary   (the platform-wide experience summary)
    submit_task        (delegate a business request to the service)

This platform observes only. It never plans, never executes a workflow or a
capability, never calls the Workflow Coordinator, and never modifies AI behaviour —
business work goes only through the :class:`AIEmployeeService`. Constructor injection
only; it holds no mutable state of its own (feedback lives in the
:class:`FeedbackManager`) — no static, singleton, or service-locator state. Strictly
additive to Sprints 1.x–16.11, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.services.ai_employee.experience.behavior_analyzer import (
    BehaviorAnalyzer,
)
from app.services.ai_employee.experience.experience_analyzer import (
    ExperienceAnalyzer,
)
from app.services.ai_employee.experience.feedback import FeedbackManager
from app.services.ai_employee.experience.friction_detector import (
    FrictionDetector,
)
from app.services.ai_employee.experience.improvement_reporter import (
    ImprovementReporter,
)
from app.services.ai_employee.experience.models import (
    BehaviorMetrics,
    ExperienceMetrics,
    FeedbackCategory,
    FeedbackRecord,
    FrictionReport,
    ImprovementRecommendation,
    ImprovementReport,
    PlatformExperienceSummary,
    QualityAssessment,
    ReportPeriod,
)
from app.services.ai_employee.experience.quality_evaluator import (
    QualityEvaluator,
)
from app.services.ai_employee.experience.recommendation_engine import (
    RecommendationEngine,
)
from app.services.ai_employee.service import (
    TaskSubmissionRequest,
    TaskSubmissionResponse,
)


class ExperienceIntelligenceManager:
    """Coordinates experience intelligence over its collaborators and the service.

    Constructed with an injected :class:`FeedbackManager`, :class:`ExperienceAnalyzer`,
    :class:`BehaviorAnalyzer`, :class:`QualityEvaluator`, :class:`FrictionDetector`,
    :class:`RecommendationEngine`, :class:`ImprovementReporter`, and the frozen Sprint
    16.10 :class:`AIEmployeeService` (constructor injection; it instantiates none). It
    collects feedback, analyses experience/behaviour/quality/friction, generates
    deterministic recommendations, assembles reports, and delegates every business
    request to the :class:`AIEmployeeService` — it observes only and executes no
    workflow itself. It holds no mutable state of its own.
    """

    def __init__(
        self,
        feedback: FeedbackManager,
        experience_analyzer: ExperienceAnalyzer,
        behavior_analyzer: BehaviorAnalyzer,
        quality_evaluator: QualityEvaluator,
        friction_detector: FrictionDetector,
        recommendation_engine: RecommendationEngine,
        reporter: ImprovementReporter,
        service,
    ) -> None:
        self.feedback = feedback
        self.experience_analyzer = experience_analyzer
        self.behavior_analyzer = behavior_analyzer
        self.quality_evaluator = quality_evaluator
        self.friction_detector = friction_detector
        self.recommendation_engine = recommendation_engine
        self.reporter = reporter
        self.service = service

    # --- feedback --------------------------------------------------------
    def record_feedback(
        self,
        rating: int,
        comment: str = "",
        category: FeedbackCategory = FeedbackCategory.GENERAL,
        workflow: str = "",
        feature: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeedbackRecord:
        """Collect one structured feedback record (delegates to the FeedbackManager)."""
        return self.feedback.submit(
            rating=rating,
            comment=comment,
            category=category,
            workflow=workflow,
            feature=feature,
            metadata=metadata,
        )

    def feedback_history(self) -> List[FeedbackRecord]:
        """Return the full feedback trail."""
        return self.feedback.history()

    def feedback_summary(self) -> Dict[str, Any]:
        """Return the deterministic feedback summary aggregates."""
        return self.feedback.summary()

    # --- analysis --------------------------------------------------------
    def experience(self) -> ExperienceMetrics:
        """Return the computed :class:`ExperienceMetrics` for the live tasks."""
        return self.experience_analyzer.analyze()

    def behavior(self) -> BehaviorMetrics:
        """Return the computed :class:`BehaviorMetrics` for the live tasks/sessions."""
        return self.behavior_analyzer.analyze()

    def quality(self) -> QualityAssessment:
        """Return the aggregate :class:`QualityAssessment` for the live tasks."""
        return self.quality_evaluator.aggregate()

    def friction(self) -> FrictionReport:
        """Return the :class:`FrictionReport` for the live tasks."""
        return self.friction_detector.detect()

    def analyze(self) -> PlatformExperienceSummary:
        """Return the full platform experience snapshot (the analysis entry point)."""
        return self._summary()

    def platform_summary(self) -> PlatformExperienceSummary:
        """Return the platform-wide experience summary (same snapshot as ``analyze``)."""
        return self._summary()

    def recommendations(self) -> List[ImprovementRecommendation]:
        """Return the deterministic, rule-based improvement recommendations."""
        experience, behavior, friction, quality = self._compute()
        return self.recommendation_engine.recommend(
            experience, behavior, friction, quality
        )

    def report(
        self, period: ReportPeriod = ReportPeriod.DAILY, sequence: int = 0
    ) -> ImprovementReport:
        """Return the assembled :class:`ImprovementReport` for ``period``."""
        experience, behavior, friction, quality = self._compute()
        recommendations = self.recommendation_engine.recommend(
            experience, behavior, friction, quality
        )
        if period == ReportPeriod.WEEKLY:
            return self.reporter.weekly_report(
                experience, behavior, friction, recommendations, sequence
            )
        if period == ReportPeriod.PLATFORM:
            return self.reporter.platform_report(
                experience, behavior, friction, recommendations, sequence
            )
        if period == ReportPeriod.CAPABILITY:
            return self.reporter.capability_report(
                experience, recommendations, sequence
            )
        return self.reporter.daily_report(
            experience, behavior, friction, recommendations, sequence
        )

    # --- business delegation --------------------------------------------
    def submit_task(
        self, request: TaskSubmissionRequest
    ) -> TaskSubmissionResponse:
        """Delegate a business task submission to the :class:`AIEmployeeService`.

        The experience platform never executes work itself: it forwards the request to
        the frozen Sprint 16.10 service (the only path to the :class:`AIEmployee`). It
        calls no Workflow Coordinator and no capability, and observes rather than
        drives.
        """
        return self.service.submit_task(request)

    # --- helpers ---------------------------------------------------------
    def _compute(
        self,
    ) -> Tuple[
        ExperienceMetrics,
        BehaviorMetrics,
        FrictionReport,
        QualityAssessment,
    ]:
        """Compute the four core analysis DTOs over one shared observation set.

        Reads the live task list once and passes it to each analyzer so every metric
        reflects the same snapshot. Deterministic; it runs nothing.
        """
        tasks = self.service.list_tasks()
        experience = self.experience_analyzer.analyze(tasks)
        behavior = self.behavior_analyzer.analyze(tasks)
        friction = self.friction_detector.detect(tasks)
        quality = self.quality_evaluator.aggregate(tasks)
        return experience, behavior, friction, quality

    def _summary(self) -> PlatformExperienceSummary:
        """Assemble the platform experience summary from the core analysis DTOs."""
        experience, behavior, friction, quality = self._compute()
        recommendations = self.recommendation_engine.recommend(
            experience, behavior, friction, quality
        )
        return self.reporter.experience_summary(
            experience,
            behavior,
            friction,
            quality,
            self.feedback.summary(),
            recommendation_count=len(recommendations),
        )
