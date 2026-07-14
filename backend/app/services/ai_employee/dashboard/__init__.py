"""Developer Dashboard package (Sprint 16.14 — visualise the platform for engineers).

Adds the Developer Dashboard — a provider-independent, *visualisation-data* surface that
gives engineers a complete operational view of the AI Employee platform over the frozen
Sprint 16.13 :class:`ProductionValidationManager`. This dashboard visualises existing
systems only: it never executes a workflow or a capability, never calls the Workflow
Coordinator, and never changes AI behaviour or modifies platform state. Platform state
is read through the frozen :class:`ProductionValidationManager`,
:class:`ExperienceIntelligenceManager`, :class:`EnterpriseOperationsManager`, and
:class:`AIEmployeeService`, and it renders no web UI, frontend, API endpoint, chart,
graph, HTML, or JavaScript — only immutable view DTOs. It follows the flow
``DeveloperDashboardManager -> {WorkflowInspector, AgentInspector, MemoryInspector,
SchedulerInspector, RecoveryInspector, CapabilityInspector, ValidationInspector,
ExperienceInspector, OperationsInspector, DashboardReporter}`` over the
:class:`ProductionValidationManager`:

* the immutable DTOs :class:`DashboardOverview`, :class:`WorkflowDashboard`,
  :class:`AgentDashboard`, :class:`MemoryDashboard`, :class:`SchedulerDashboard`,
  :class:`RecoveryDashboard`, :class:`CapabilityDashboard`, :class:`ValidationDashboard`,
  :class:`ExperienceDashboard`, :class:`OperationsDashboard`, and
  :class:`DashboardReport`, plus the :class:`ReportKind` enum;
* the nine inspectors and the :class:`DashboardReporter`; and
* the :class:`DeveloperDashboardManager` coordinator.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.13.
"""

from app.services.ai_employee.dashboard.agent_inspector import AgentInspector
from app.services.ai_employee.dashboard.capability_inspector import (
    CapabilityInspector,
)
from app.services.ai_employee.dashboard.experience_inspector import (
    ExperienceInspector,
)
from app.services.ai_employee.dashboard.manager import (
    DeveloperDashboardManager,
)
from app.services.ai_employee.dashboard.memory_inspector import (
    MemoryInspector,
)
from app.services.ai_employee.dashboard.models import (
    AgentDashboard,
    CapabilityDashboard,
    DashboardOverview,
    DashboardReport,
    ExperienceDashboard,
    MemoryDashboard,
    OperationsDashboard,
    RecoveryDashboard,
    ReportKind,
    SchedulerDashboard,
    ValidationDashboard,
    WorkflowDashboard,
)
from app.services.ai_employee.dashboard.operations_inspector import (
    OperationsInspector,
)
from app.services.ai_employee.dashboard.recovery_inspector import (
    RecoveryInspector,
)
from app.services.ai_employee.dashboard.reporter import DashboardReporter
from app.services.ai_employee.dashboard.scheduler_inspector import (
    SchedulerInspector,
)
from app.services.ai_employee.dashboard.validation_inspector import (
    ValidationInspector,
)
from app.services.ai_employee.dashboard.workflow_inspector import (
    WorkflowInspector,
)

__all__ = [
    # DTOs
    "DashboardOverview",
    "WorkflowDashboard",
    "AgentDashboard",
    "MemoryDashboard",
    "SchedulerDashboard",
    "RecoveryDashboard",
    "CapabilityDashboard",
    "ValidationDashboard",
    "ExperienceDashboard",
    "OperationsDashboard",
    "DashboardReport",
    # enum
    "ReportKind",
    # inspectors / reporter / manager
    "WorkflowInspector",
    "AgentInspector",
    "MemoryInspector",
    "SchedulerInspector",
    "RecoveryInspector",
    "CapabilityInspector",
    "ValidationInspector",
    "ExperienceInspector",
    "OperationsInspector",
    "DashboardReporter",
    "DeveloperDashboardManager",
]
