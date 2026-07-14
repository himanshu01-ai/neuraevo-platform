"""Experience Intelligence Platform package (Sprint 16.12 — observe experience).

Adds the Experience Intelligence & Continuous Improvement Platform — a
provider-independent, *observational* surface that measures real user experience, AI
task quality, and workflow friction, and generates deterministic improvement insights
over the frozen Sprint 16.10 :class:`AIEmployeeService`. This platform observes only:
it never plans, never executes a workflow or a capability, never calls the Workflow
Coordinator, and never modifies AI behaviour. Business work is delegated to the
:class:`AIEmployeeService` alone, and it connects to no machine-learning model,
prediction engine, prompt optimiser, LLM evaluator, cloud analytics service, telemetry
SDK, HTTP transport, or database. It follows the flow ``ExperienceIntelligenceManager
-> {FeedbackManager, ExperienceAnalyzer, BehaviorAnalyzer, QualityEvaluator,
FrictionDetector, RecommendationEngine, ImprovementReporter}`` over the
:class:`AIEmployeeService`:

* the immutable DTOs :class:`FeedbackRecord`, :class:`ExperienceMetrics`,
  :class:`BehaviorMetrics`, :class:`QualityAssessment`, :class:`FrictionPoint`,
  :class:`FrictionReport`, :class:`ImprovementRecommendation`,
  :class:`ImprovementReport`, and :class:`PlatformExperienceSummary`, plus the
  :class:`FeedbackCategory`, :class:`FrictionType`, :class:`FrictionSeverity`,
  :class:`RecommendationCategory`, :class:`RecommendationPriority`,
  :class:`ExperienceGrade`, and :class:`ReportPeriod` enums;
* the :class:`FeedbackManager`, :class:`ExperienceAnalyzer`,
  :class:`BehaviorAnalyzer`, :class:`QualityEvaluator`, :class:`FrictionDetector`,
  :class:`RecommendationEngine`, and :class:`ImprovementReporter`; and
* the :class:`ExperienceIntelligenceManager` coordinator.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.11.
"""

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
from app.services.ai_employee.experience.manager import (
    ExperienceIntelligenceManager,
)
from app.services.ai_employee.experience.models import (
    BehaviorMetrics,
    ExperienceGrade,
    ExperienceMetrics,
    FeedbackCategory,
    FeedbackRecord,
    FrictionPoint,
    FrictionReport,
    FrictionSeverity,
    FrictionType,
    ImprovementRecommendation,
    ImprovementReport,
    PlatformExperienceSummary,
    QualityAssessment,
    RecommendationCategory,
    RecommendationPriority,
    ReportPeriod,
)
from app.services.ai_employee.experience.quality_evaluator import (
    QualityEvaluator,
)
from app.services.ai_employee.experience.recommendation_engine import (
    RecommendationEngine,
)

__all__ = [
    # DTOs
    "FeedbackRecord",
    "ExperienceMetrics",
    "BehaviorMetrics",
    "QualityAssessment",
    "FrictionPoint",
    "FrictionReport",
    "ImprovementRecommendation",
    "ImprovementReport",
    "PlatformExperienceSummary",
    # enums
    "FeedbackCategory",
    "FrictionType",
    "FrictionSeverity",
    "RecommendationCategory",
    "RecommendationPriority",
    "ExperienceGrade",
    "ReportPeriod",
    # managers / collaborators
    "FeedbackManager",
    "ExperienceAnalyzer",
    "BehaviorAnalyzer",
    "QualityEvaluator",
    "FrictionDetector",
    "RecommendationEngine",
    "ImprovementReporter",
    "ExperienceIntelligenceManager",
]
