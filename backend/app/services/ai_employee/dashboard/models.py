"""Developer Dashboard models (Sprint 16.14 — immutable dashboard DTOs).

Provider-independent, immutable DTOs and the report-kind enum for the Developer
Dashboard — the *visualisation-data* surface that gives engineers a complete
operational view of the AI Employee platform over the frozen Sprint 16.13
:class:`ProductionValidationManager`. This dashboard visualises existing systems only:
it never executes a workflow, never changes AI behaviour, and never modifies platform
state. It reads platform state and produces structured view DTOs.

These are plain-data view models: there is no web UI, frontend, API endpoint, chart,
graph, visualisation library, HTML, or JavaScript anywhere — never a provider/SDK
object crosses the boundary. Each DTO simply carries the already-computed numbers a
developer tool would render. Strictly additive to Sprints 1.x–16.13, whose modules are
left untouched.
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
class ReportKind(str, Enum):
    """The allowed, deterministic kinds of dashboard report.

    ``OVERVIEW`` — the compact health/readiness roll-up. ``ENGINEERING`` — the full
    engineering dashboard (every inspector). ``SYSTEM`` — the system-focused view.
    ``DAILY`` — the daily dashboard. Kept as a ``str`` enum so each serialises to its
    label.
    """

    OVERVIEW = "OVERVIEW"
    ENGINEERING = "ENGINEERING"
    SYSTEM = "SYSTEM"
    DAILY = "DAILY"


# =====================================================================
# Per-inspector view DTOs
# =====================================================================
class DashboardOverview(BaseModel):
    """Immutable compact roll-up of the whole platform (no execution).

    ``frozen=True`` makes instances immutable. ``ready`` is the production-readiness
    verdict; ``state`` is the overall health-state label; ``grade`` is the experience
    grade; ``healthy_subsystems``/``total_subsystems`` count subsystem health;
    ``total_tasks`` and ``active_sessions`` count work; ``open_issues`` is the blocking
    issue count; ``feedback_count`` is how much feedback exists; ``summary`` is a
    plain-text line; and ``overview_metadata`` carries plain descriptors. Producing this
    DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    ready: bool = False
    state: str = ""
    grade: str = ""
    healthy_subsystems: int = Field(default=0, ge=0)
    total_subsystems: int = Field(default=0, ge=0)
    total_tasks: int = Field(default=0, ge=0)
    active_sessions: int = Field(default=0, ge=0)
    open_issues: int = Field(default=0, ge=0)
    feedback_count: int = Field(default=0, ge=0)
    summary: str = ""
    overview_metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowDashboard(BaseModel):
    """Immutable view of workflow status, history, lifecycle, and progress.

    ``frozen=True`` makes instances immutable. ``total`` is how many workflows/tasks
    were observed; ``status_counts`` maps each lifecycle state to a count; ``history``
    is the per-workflow record list; ``progress`` maps progress ratios/counters; and
    ``dashboard_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    total: int = Field(default=0, ge=0)
    status_counts: Dict[str, int] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    progress: Dict[str, float] = Field(default_factory=dict)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentDashboard(BaseModel):
    """Immutable view of registered agents, status, active work, and coordination.

    ``frozen=True`` makes instances immutable. ``registered_agents`` lists the observed
    agent ids; ``agent_count`` is their number; ``active_work`` is the count of active
    engagements; ``session_counts`` maps session totals; ``coordination`` maps
    coordination counters; and ``dashboard_metadata`` carries plain descriptors.
    Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    registered_agents: List[str] = Field(default_factory=list)
    agent_count: int = Field(default=0, ge=0)
    active_work: int = Field(default=0, ge=0)
    session_counts: Dict[str, int] = Field(default_factory=dict)
    coordination: Dict[str, int] = Field(default_factory=dict)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryDashboard(BaseModel):
    """Immutable view of the memory subsystem summary, categories, and statistics.

    ``frozen=True`` makes instances immutable. ``present``/``healthy`` and ``state``
    report the memory subsystem status; ``categories`` maps each observed memory
    category to a count; ``statistics`` maps memory counters; and ``dashboard_metadata``
    carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    present: bool = False
    healthy: bool = False
    state: str = ""
    categories: Dict[str, int] = Field(default_factory=dict)
    statistics: Dict[str, int] = Field(default_factory=dict)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class SchedulerDashboard(BaseModel):
    """Immutable view of scheduled workflows, the queue, and execution.

    ``frozen=True`` makes instances immutable. ``present``/``healthy`` and ``state``
    report the scheduler subsystem status; ``scheduled_workflows`` is how many were
    observed; ``queue_summary`` maps queue-state counters; ``execution_summary`` maps
    execution counters; and ``dashboard_metadata`` carries plain descriptors. Producing
    this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    present: bool = False
    healthy: bool = False
    state: str = ""
    scheduled_workflows: int = Field(default=0, ge=0)
    queue_summary: Dict[str, int] = Field(default_factory=dict)
    execution_summary: Dict[str, int] = Field(default_factory=dict)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryDashboard(BaseModel):
    """Immutable view of recovery history, retry statistics, and failures.

    ``frozen=True`` makes instances immutable. ``present``/``healthy`` and ``state``
    report the recovery subsystem status; ``recovery_history`` lists the observed
    recovery records; ``retry_statistics`` maps retry counters; ``failure_summary`` maps
    failure counters; and ``dashboard_metadata`` carries plain descriptors. Producing
    this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    present: bool = False
    healthy: bool = False
    state: str = ""
    recovery_history: List[Dict[str, Any]] = Field(default_factory=list)
    retry_statistics: Dict[str, int] = Field(default_factory=dict)
    failure_summary: Dict[str, int] = Field(default_factory=dict)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityDashboard(BaseModel):
    """Immutable view of capability usage, execution statistics, and success rates.

    ``frozen=True`` makes instances immutable. ``capability_usage`` maps each capability
    to an invocation count; ``success_rates`` maps each capability to its success
    fraction; ``execution`` maps aggregate execution counters; and
    ``dashboard_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    capability_usage: Dict[str, int] = Field(default_factory=dict)
    success_rates: Dict[str, float] = Field(default_factory=dict)
    execution: Dict[str, Any] = Field(default_factory=dict)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationDashboard(BaseModel):
    """Immutable view of production readiness, validation reports, and issues.

    ``frozen=True`` makes instances immutable. ``ready`` is the readiness verdict;
    ``state`` is the health-state label; ``passed_validations``/``total_validations``
    count the validations; ``results`` lists each validation result; ``issues`` lists
    the blocking issues; and ``dashboard_metadata`` carries plain descriptors. Producing
    this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    ready: bool = False
    state: str = ""
    passed_validations: int = Field(default=0, ge=0)
    total_validations: int = Field(default=0, ge=0)
    results: List[Dict[str, Any]] = Field(default_factory=list)
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperienceDashboard(BaseModel):
    """Immutable view of feedback, quality metrics, friction, and recommendations.

    ``frozen=True`` makes instances immutable. ``grade`` is the experience grade;
    ``feedback_summary`` carries the feedback aggregates; ``quality`` carries the
    aggregate quality assessment; ``friction`` carries the friction roll-up;
    ``recommendations`` lists the improvement recommendations; and
    ``dashboard_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    grade: str = ""
    feedback_summary: Dict[str, Any] = Field(default_factory=dict)
    quality: Dict[str, Any] = Field(default_factory=dict)
    friction: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


class OperationsDashboard(BaseModel):
    """Immutable view of audit, authorization, configuration, deployment, diagnostics.

    ``frozen=True`` makes instances immutable. ``audit_summary`` maps each audit
    category to a count; ``authorization_summary`` carries authorization descriptors;
    ``configuration_status`` and ``deployment_status`` carry their readiness
    descriptors; ``diagnostics`` carries the diagnostics roll-up; and
    ``dashboard_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    audit_summary: Dict[str, int] = Field(default_factory=dict)
    authorization_summary: Dict[str, Any] = Field(default_factory=dict)
    configuration_status: Dict[str, Any] = Field(default_factory=dict)
    deployment_status: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    dashboard_metadata: Dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Composite report DTO
# =====================================================================
class DashboardReport(BaseModel):
    """Immutable composite dashboard report bundling the inspector views (no execution).

    ``frozen=True`` makes instances immutable. ``report_id`` names the report; ``kind``
    is its :class:`ReportKind`; ``overview`` is the always-present roll-up; the per-
    inspector fields (``workflow`` … ``operations``) are populated for the sections the
    report covers and left ``None`` otherwise; ``highlights`` are plain-text headline
    lines; ``generated_sequence`` is a deterministic ordinal (an integer, never a clock
    time); and ``report_metadata`` carries plain descriptors. This is a pure read —
    producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    report_id: _NonEmptyStr
    kind: ReportKind
    overview: DashboardOverview
    workflow: Optional[WorkflowDashboard] = None
    agent: Optional[AgentDashboard] = None
    memory: Optional[MemoryDashboard] = None
    scheduler: Optional[SchedulerDashboard] = None
    recovery: Optional[RecoveryDashboard] = None
    capability: Optional[CapabilityDashboard] = None
    validation: Optional[ValidationDashboard] = None
    experience: Optional[ExperienceDashboard] = None
    operations: Optional[OperationsDashboard] = None
    highlights: List[str] = Field(default_factory=list)
    generated_sequence: int = Field(default=0, ge=0)
    report_metadata: Dict[str, Any] = Field(default_factory=dict)
