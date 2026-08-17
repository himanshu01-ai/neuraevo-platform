"""Experience Intelligence Platform models (Sprint 16.12 — immutable experience DTOs).

Provider-independent, immutable DTOs and enums for the Experience Intelligence &
Continuous Improvement Platform — the *observational* surface that measures real user
experience, AI task quality, and workflow friction over the frozen Sprint 16.10
:class:`AIEmployeeService`. This platform observes only: it never plans, never
executes a workflow, and never modifies AI behaviour. It reads platform state and
collected feedback and computes deterministic, rule-based insights.

There is no machine learning, prediction, prompt optimisation, LLM evaluation, cloud
analytics, telemetry SDK, HTTP, REST, or database anywhere. These carry only plain
data — never a provider/SDK object crosses the boundary. Strictly additive to Sprints
1.x–16.11, whose modules are left untouched.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Enums
# =====================================================================
class FeedbackCategory(str, Enum):
    """The allowed, deterministic categories a feedback record can carry.

    ``TASK`` — feedback about a task outcome. ``WORKFLOW`` — about a workflow.
    ``CAPABILITY`` — about a capability. ``FEATURE`` — about a product feature.
    ``EXPERIENCE`` — about overall experience. ``GENERAL`` — uncategorised. Kept as a
    ``str`` enum so each serialises to its label.
    """

    TASK = "TASK"
    WORKFLOW = "WORKFLOW"
    CAPABILITY = "CAPABILITY"
    FEATURE = "FEATURE"
    EXPERIENCE = "EXPERIENCE"
    GENERAL = "GENERAL"


class FrictionType(str, Enum):
    """The allowed, deterministic kinds of workflow friction the platform detects.

    ``FREQUENT_FAILURES`` — a high task failure rate. ``REPEATED_RETRIES`` — tasks
    retried repeatedly. ``LONG_WORKFLOWS`` — workflows with many steps. ``ABANDONED
    _TASKS`` — tasks left unfinished. ``HIGH_CANCELLATION`` — a high cancellation rate.
    Kept as a ``str`` enum so each serialises to its label.
    """

    FREQUENT_FAILURES = "FREQUENT_FAILURES"
    REPEATED_RETRIES = "REPEATED_RETRIES"
    LONG_WORKFLOWS = "LONG_WORKFLOWS"
    ABANDONED_TASKS = "ABANDONED_TASKS"
    HIGH_CANCELLATION = "HIGH_CANCELLATION"


class FrictionSeverity(str, Enum):
    """The allowed, deterministic severities of a detected friction point.

    ``NONE`` — below any threshold (not reported). ``LOW`` / ``MEDIUM`` / ``HIGH`` —
    increasing concern. Kept as a ``str`` enum so each serialises to its label.
    """

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendationCategory(str, Enum):
    """The allowed, deterministic categories of an improvement recommendation.

    ``CAPABILITY`` — improve a capability. ``WORKFLOW`` — improve workflow shape.
    ``APPROVAL`` — optimise the approval flow. ``RECOVERY`` — improve recovery.
    ``QUALITY`` — improve output/task quality. ``EXPERIENCE`` — improve overall
    experience. Kept as a ``str`` enum so each serialises to its label.
    """

    CAPABILITY = "CAPABILITY"
    WORKFLOW = "WORKFLOW"
    APPROVAL = "APPROVAL"
    RECOVERY = "RECOVERY"
    QUALITY = "QUALITY"
    EXPERIENCE = "EXPERIENCE"


class RecommendationPriority(str, Enum):
    """The allowed, deterministic priorities of an improvement recommendation."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExperienceGrade(str, Enum):
    """The allowed, deterministic overall experience grades for the platform.

    ``EXCELLENT`` / ``GOOD`` / ``FAIR`` / ``POOR`` — decreasing quality, derived from
    the deterministic success, quality, and friction signals. Kept as a ``str`` enum so
    each serialises to its label.
    """

    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"


class ReportPeriod(str, Enum):
    """The allowed, deterministic scopes of an improvement report.

    ``DAILY`` / ``WEEKLY`` — periodic summaries. ``PLATFORM`` — the full platform
    report. ``CAPABILITY`` — a capability-focused report. Kept as a ``str`` enum so each
    serialises to its label.
    """

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    PLATFORM = "PLATFORM"
    CAPABILITY = "CAPABILITY"


# =====================================================================
# DTOs
# =====================================================================
class FeedbackRecord(BaseModel):
    """Immutable record of one piece of structured user feedback (no execution).

    ``frozen=True`` makes instances immutable. ``feedback_id`` names the record;
    ``rating`` is a 1–5 star rating; ``comment`` is free text; ``category`` is its
    :class:`FeedbackCategory`; ``workflow`` and ``feature`` name what the feedback is
    about (either may be blank); ``sequence`` is a deterministic ordinal (an integer,
    never a clock time); and ``feedback_metadata`` carries plain descriptors. Producing
    this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    feedback_id: _NonEmptyStr
    rating: int = Field(ge=1, le=5)
    comment: str = ""
    category: FeedbackCategory = FeedbackCategory.GENERAL
    workflow: str = ""
    feature: str = ""
    sequence: int = Field(default=0, ge=0)
    feedback_metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperienceMetrics(BaseModel):
    """Immutable aggregate of task-experience measurements (no execution).

    ``frozen=True`` makes instances immutable. ``task_count`` is how many tasks were
    observed; ``task_success_rate`` and ``workflow_completion_rate`` are fractions in
    ``[0, 1]``; ``average_execution_units`` is the mean deterministic execution size
    (a step-count proxy for duration, never wall-clock time); ``approval_rate`` and
    ``recovery_rate`` are fractions of tasks that needed approval/recovery;
    ``capability_success`` maps each observed capability to its success fraction; and
    ``metrics_metadata`` carries plain descriptors. This is a pure read — producing it
    runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    task_count: int = Field(default=0, ge=0)
    task_success_rate: float = 0.0
    workflow_completion_rate: float = 0.0
    average_execution_units: float = 0.0
    approval_rate: float = 0.0
    recovery_rate: float = 0.0
    capability_success: Dict[str, float] = Field(default_factory=dict)
    metrics_metadata: Dict[str, Any] = Field(default_factory=dict)


class BehaviorMetrics(BaseModel):
    """Immutable aggregate of usage-behaviour measurements (no execution).

    ``frozen=True`` makes instances immutable. ``feature_usage``, ``capability_usage``,
    and ``workflow_frequency`` map each observed name to its usage count;
    ``repeat_usage`` maps the names used more than once to that count;
    ``total_sessions`` and ``active_sessions`` count sessions; and
    ``metrics_metadata`` carries plain descriptors. This is a pure read — producing it
    runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    feature_usage: Dict[str, int] = Field(default_factory=dict)
    capability_usage: Dict[str, int] = Field(default_factory=dict)
    workflow_frequency: Dict[str, int] = Field(default_factory=dict)
    repeat_usage: Dict[str, int] = Field(default_factory=dict)
    total_sessions: int = Field(default=0, ge=0)
    active_sessions: int = Field(default=0, ge=0)
    metrics_metadata: Dict[str, Any] = Field(default_factory=dict)


class QualityAssessment(BaseModel):
    """Immutable quality evaluation of one task (or an aggregate) (no execution).

    ``frozen=True`` makes instances immutable. ``task_id`` names the evaluated task (or
    an aggregate label); ``goal_achieved`` and ``output_accepted`` are the deterministic
    quality flags; ``retry_count`` is how many retries occurred; ``approval_required``
    and ``recovery_required`` flag whether human approval / recovery was needed;
    ``quality_score`` is a deterministic score in ``[0, 100]``; and
    ``assessment_metadata`` carries plain descriptors. This is a pure read — producing
    it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str = ""
    goal_achieved: bool = False
    output_accepted: bool = False
    retry_count: int = Field(default=0, ge=0)
    approval_required: bool = False
    recovery_required: bool = False
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0)
    assessment_metadata: Dict[str, Any] = Field(default_factory=dict)


class FrictionPoint(BaseModel):
    """Immutable description of one detected friction point (no execution).

    ``frozen=True`` makes instances immutable. ``friction_type`` is its
    :class:`FrictionType`; ``severity`` its :class:`FrictionSeverity`; ``detail`` a
    plain-text explanation; ``metric`` the deterministic measured value that triggered
    it; and ``point_metadata`` carries plain descriptors. Producing this DTO runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    friction_type: FrictionType
    severity: FrictionSeverity
    detail: str = ""
    metric: float = 0.0
    point_metadata: Dict[str, Any] = Field(default_factory=dict)


class FrictionReport(BaseModel):
    """Immutable report of detected workflow friction (no execution).

    ``frozen=True`` makes instances immutable. ``friction_detected`` is whether any
    friction rose above a threshold; ``points`` are the per-type :class:`FrictionPoint`
    s; ``highest_severity`` is the maximum reported :class:`FrictionSeverity`;
    ``summary`` is a plain-text summary; and ``report_metadata`` carries plain
    descriptors. This is a pure read — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    friction_detected: bool = False
    points: List[FrictionPoint] = Field(default_factory=list)
    highest_severity: FrictionSeverity = FrictionSeverity.NONE
    summary: str = ""
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class ImprovementRecommendation(BaseModel):
    """Immutable, deterministic improvement recommendation (rule-based, no execution).

    ``frozen=True`` makes instances immutable. ``recommendation_id`` names the
    recommendation; ``category`` is its :class:`RecommendationCategory`; ``priority``
    its :class:`RecommendationPriority`; ``title`` a short deterministic headline;
    ``detail`` a plain-text description; ``rationale`` the deterministic reason it was
    produced; ``target`` names what it concerns (e.g. a capability or workflow); and
    ``recommendation_metadata`` carries plain descriptors. It is produced by
    deterministic rules — never by AI generation. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    recommendation_id: _NonEmptyStr
    category: RecommendationCategory
    priority: RecommendationPriority
    title: _NonEmptyStr
    detail: str = ""
    rationale: str = ""
    target: str = ""
    recommendation_metadata: Dict[str, Any] = Field(default_factory=dict)


class ImprovementReport(BaseModel):
    """Immutable improvement report over a chosen scope (no execution).

    ``frozen=True`` makes instances immutable. ``report_id`` names the report;
    ``period`` is its :class:`ReportPeriod` scope; ``generated_sequence`` is a
    deterministic ordinal (an integer, never a clock time); ``experience``,
    ``behavior``, and ``friction`` are the optional bundled metric DTOs;
    ``recommendations`` are the deterministic :class:`ImprovementRecommendation` s;
    ``highlights`` are plain-text headline lines; and ``report_metadata`` carries plain
    descriptors. This is a pure read — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    report_id: _NonEmptyStr
    period: ReportPeriod
    generated_sequence: int = Field(default=0, ge=0)
    experience: Optional[ExperienceMetrics] = None
    behavior: Optional[BehaviorMetrics] = None
    friction: Optional[FrictionReport] = None
    recommendations: List[ImprovementRecommendation] = Field(
        default_factory=list
    )
    highlights: List[str] = Field(default_factory=list)
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class PlatformExperienceSummary(BaseModel):
    """Immutable, platform-wide experience snapshot (no execution).

    ``frozen=True`` makes instances immutable. ``grade`` is the overall
    :class:`ExperienceGrade`; ``experience``, ``behavior``, ``friction``, and
    ``quality`` are the bundled analysis DTOs (``quality`` is the aggregate
    :class:`QualityAssessment`); ``feedback_count`` and ``average_rating`` summarise
    collected feedback; ``recommendation_count`` is how many recommendations were
    produced; ``summary`` is a plain-text summary; and ``summary_metadata`` carries
    plain descriptors. This is a pure read — producing it runs nothing and exposes no
    provider object.
    """

    model_config = ConfigDict(frozen=True)

    grade: ExperienceGrade
    experience: ExperienceMetrics
    behavior: BehaviorMetrics
    friction: FrictionReport
    quality: QualityAssessment
    feedback_count: int = Field(default=0, ge=0)
    average_rating: float = 0.0
    recommendation_count: int = Field(default=0, ge=0)
    summary: str = ""
    summary_metadata: Dict[str, Any] = Field(default_factory=dict)
