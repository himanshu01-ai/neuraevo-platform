"""Developer Dashboard manager (Sprint 16.14 — coordinate dashboard generation).

Defines :class:`DeveloperDashboardManager`, the coordinator of the Developer Dashboard.
It coordinates the dashboard over its injected inspectors — the
:class:`WorkflowInspector`, :class:`AgentInspector`, :class:`MemoryInspector`,
:class:`SchedulerInspector`, :class:`RecoveryInspector`, :class:`CapabilityInspector`,
:class:`ValidationInspector`, :class:`ExperienceInspector`, and
:class:`OperationsInspector` — and the :class:`DashboardReporter`, and *delegates to the
frozen Sprint 16.13* :class:`ProductionValidationManager` for the platform's overall
state:

    overview        (the compact platform roll-up)
    dashboard       (the full engineering dashboard)
    system_view     (the system-focused dashboard)
    health_view     (the health/readiness overview dashboard)
    report          (a dashboard report of the requested kind)

This dashboard visualises existing systems only. It never executes a workflow or a
capability, never calls the Workflow Coordinator, and never changes AI behaviour or
modifies platform state — it reads only. Constructor injection only; it holds no mutable
state of its own — no static, singleton, or service-locator state. Strictly additive to
Sprints 1.x–16.13, whose modules are left untouched.
"""

from typing import Any, Dict

from app.services.ai_employee.dashboard.models import (
    AgentDashboard,
    DashboardOverview,
    DashboardReport,
    ExperienceDashboard,
    ReportKind,
    WorkflowDashboard,
)

# The system-focused sections included in ``system_view``.
_SYSTEM_SECTIONS = (
    "workflow",
    "agent",
    "memory",
    "scheduler",
    "recovery",
    "capability",
)

# The health-focused sections included in ``health_view``.
_HEALTH_SECTIONS = ("validation", "operations")


class DeveloperDashboardManager:
    """Coordinates dashboard generation over its inspectors and the reporter.

    Constructed with an injected :class:`WorkflowInspector`, :class:`AgentInspector`,
    :class:`MemoryInspector`, :class:`SchedulerInspector`, :class:`RecoveryInspector`,
    :class:`CapabilityInspector`, :class:`ValidationInspector`,
    :class:`ExperienceInspector`, :class:`OperationsInspector`,
    :class:`DashboardReporter`, and the frozen Sprint 16.13
    :class:`ProductionValidationManager` (constructor injection; it instantiates none).
    It projects each inspector's view, derives the overview from the production validator,
    and assembles reports — it visualises only and executes no workflow. It holds no
    mutable state of its own.
    """

    def __init__(
        self,
        workflow,
        agent,
        memory,
        scheduler,
        recovery,
        capability,
        validation,
        experience,
        operations,
        reporter,
        production,
    ) -> None:
        self.workflow = workflow
        self.agent = agent
        self.memory = memory
        self.scheduler = scheduler
        self.recovery = recovery
        self.capability = capability
        self.validation = validation
        self.experience = experience
        self.operations = operations
        self.reporter = reporter
        self.production = production

    # --- overview --------------------------------------------------------
    def overview(self) -> DashboardOverview:
        """Return the compact :class:`DashboardOverview` of the whole platform."""
        return self._overview(
            self.experience.dashboard(),
            self.workflow.dashboard(),
            self.agent.dashboard(),
        )

    # --- reports ---------------------------------------------------------
    def dashboard(self, sequence: int = 0) -> DashboardReport:
        """Return the full engineering :class:`DashboardReport`."""
        sections = self._all_sections()
        overview = self._overview(
            sections["experience"],
            sections["workflow"],
            sections["agent"],
        )
        return self.reporter.engineering_dashboard(
            overview, sections, sequence
        )

    def system_view(self, sequence: int = 0) -> DashboardReport:
        """Return the system-focused :class:`DashboardReport`."""
        sections = self._all_sections()
        overview = self._overview(
            sections["experience"],
            sections["workflow"],
            sections["agent"],
        )
        subset = {key: sections[key] for key in _SYSTEM_SECTIONS}
        return self.reporter.system_report(overview, subset, sequence)

    def health_view(self, sequence: int = 0) -> DashboardReport:
        """Return the health/readiness overview :class:`DashboardReport`."""
        sections = self._all_sections()
        overview = self._overview(
            sections["experience"],
            sections["workflow"],
            sections["agent"],
        )
        subset = {key: sections[key] for key in _HEALTH_SECTIONS}
        return self.reporter.overview_dashboard(overview, subset, sequence)

    def report(
        self, kind: ReportKind = ReportKind.ENGINEERING, sequence: int = 0
    ) -> DashboardReport:
        """Return the :class:`DashboardReport` for the requested ``kind``."""
        if kind == ReportKind.OVERVIEW:
            return self.health_view(sequence)
        if kind == ReportKind.SYSTEM:
            return self.system_view(sequence)
        if kind == ReportKind.DAILY:
            sections = self._all_sections()
            overview = self._overview(
                sections["experience"],
                sections["workflow"],
                sections["agent"],
            )
            return self.reporter.daily_dashboard(
                overview, sections, sequence
            )
        return self.dashboard(sequence)

    # --- helpers ---------------------------------------------------------
    def _all_sections(self) -> Dict[str, Any]:
        """Project every inspector's view into a section mapping (one read each)."""
        return {
            "workflow": self.workflow.dashboard(),
            "agent": self.agent.dashboard(),
            "memory": self.memory.dashboard(),
            "scheduler": self.scheduler.dashboard(),
            "recovery": self.recovery.dashboard(),
            "capability": self.capability.dashboard(),
            "validation": self.validation.dashboard(),
            "experience": self.experience.dashboard(),
            "operations": self.operations.dashboard(),
        }

    def _overview(
        self,
        experience: ExperienceDashboard,
        workflow: WorkflowDashboard,
        agent: AgentDashboard,
    ) -> DashboardOverview:
        """Derive the :class:`DashboardOverview` from the production validator + sections.

        The platform's overall readiness/state and subsystem health come from the frozen
        :class:`ProductionValidationManager` (the single platform state the manager
        delegates to); the grade, workflow, session, and feedback figures come from the
        already-projected sections. Deterministic; it runs nothing.
        """
        readiness = self.production.readiness()
        systems = self.production.system_statuses()
        healthy = sum(1 for status in systems if status.healthy)
        feedback_count = int(experience.feedback_summary.get("count", 0))
        return DashboardOverview(
            ready=readiness.ready,
            state=readiness.state.value,
            grade=experience.grade,
            healthy_subsystems=healthy,
            total_subsystems=len(systems),
            total_tasks=workflow.total,
            active_sessions=agent.active_work,
            open_issues=len(readiness.blocking_issues),
            feedback_count=feedback_count,
            summary=(
                f"{'ready' if readiness.ready else 'not ready'}; "
                f"grade {experience.grade}; "
                f"{healthy}/{len(systems)} subsystems healthy; "
                f"{workflow.total} workflow(s)"
            ),
            overview_metadata={
                "blocking_issues": len(readiness.blocking_issues)
            },
        )
