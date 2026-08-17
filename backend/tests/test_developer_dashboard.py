"""Unit + integration tests for the Sprint 16.14 Developer Dashboard.

Exercises the dashboard subsystem: the nine inspectors (:class:`WorkflowInspector`,
:class:`AgentInspector`, :class:`MemoryInspector`, :class:`SchedulerInspector`,
:class:`RecoveryInspector`, :class:`CapabilityInspector`, :class:`ValidationInspector`,
:class:`ExperienceInspector`, :class:`OperationsInspector`), the
:class:`DashboardReporter`, and the :class:`DeveloperDashboardManager` that coordinates
them over the frozen Sprint 16.13 :class:`ProductionValidationManager`.

The Developer Dashboard visualises existing systems only — it never executes a workflow,
never changes AI behaviour, and never modifies platform state. It reads state through
the frozen production validator, experience, operations, and service managers (which
here run over deterministic recording doubles), and it renders no web UI, endpoint,
chart, or HTML — only immutable view DTOs.

Covers, as the sprint requires: dashboard overview, all inspectors, dashboard reports,
DTO immutability, DI wiring, and regression (Sprints 16.1–16.13 unchanged; the dashboard
sub-package imports no Workflow Coordinator, capability, repository, LLM provider,
database, HTTP, or frontend/chart facility). Also asserts the read-only invariant: the
audit trail is unchanged by dashboard generation.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_developer_dashboard
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import AIEmployee, EmployeeProfile
from app.services.ai_employee.dashboard import (
    AgentDashboard,
    AgentInspector,
    CapabilityDashboard,
    CapabilityInspector,
    DashboardOverview,
    DashboardReport,
    DashboardReporter,
    DeveloperDashboardManager,
    ExperienceDashboard,
    ExperienceInspector,
    MemoryDashboard,
    MemoryInspector,
    OperationsDashboard,
    OperationsInspector,
    RecoveryDashboard,
    RecoveryInspector,
    ReportKind,
    SchedulerDashboard,
    SchedulerInspector,
    ValidationDashboard,
    ValidationInspector,
    WorkflowDashboard,
    WorkflowInspector,
)
from app.services.ai_employee.experience import (
    BehaviorAnalyzer,
    ExperienceAnalyzer,
    ExperienceIntelligenceManager,
    FeedbackManager,
    FrictionDetector,
    ImprovementReporter,
    QualityEvaluator,
    RecommendationEngine,
)
from app.services.ai_employee.operations import (
    AuditManager,
    ConfigurationManager,
    DeploymentValidator,
    DiagnosticsManager,
    EnterpriseOperationsManager,
    LocalAuthorizationManager,
    ObservabilityManager,
)
from app.services.ai_employee.service import (
    AIEmployeeService,
    ErrorMapper,
    HealthManager,
    IdempotencyManager,
    RequestValidator,
    ResponseBuilder,
    SessionManager,
    TaskSubmissionRequest,
)
from app.services.ai_employee.service.health import HEALTH_COMPONENTS
from app.services.ai_employee.validation import (
    CompatibilityValidator,
    IntegrationValidator,
    PerformanceValidator,
    ProductionValidationManager,
    ReliabilityValidator,
    SecurityValidator,
    SystemValidator,
    ValidationReporter,
)
from app.services.planning.models import ExecutionPlan
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

_COMPLETED = WorkflowStatus.COMPLETED.value


# =====================================================================
# Offline recording doubles + helpers
# =====================================================================
class _RecordingPlanningEngine:
    def create_plan(self, request) -> ExecutionPlan:
        return ExecutionPlan(goal="g", summary="s")


class _RecordingWorkflowCoordinator:
    def __init__(self, status: str = _COMPLETED) -> None:
        self._status = status

    def execute(
        self,
        steps,
        workflow_id="workflow",
        runtime_id="",
        execution_id="",
        initial_inputs=None,
    ) -> WorkflowExecutionResult:
        return WorkflowExecutionResult(
            workflow_id=workflow_id,
            workflow_status=self._status,
            total_step_count=len(steps),
        )


def _service(components=None) -> AIEmployeeService:
    ai = AIEmployee(
        _RecordingPlanningEngine(), _RecordingWorkflowCoordinator()
    )
    health = HealthManager(
        components or {name: True for name in HEALTH_COMPONENTS}
    )
    return AIEmployeeService(
        ai,
        SessionManager(),
        RequestValidator(),
        ResponseBuilder(),
        IdempotencyManager(),
        health,
        ErrorMapper(),
    )


def _operations(components=None) -> EnterpriseOperationsManager:
    service = _service(components)
    health = service.health_manager
    audit = AuditManager()
    config = ConfigurationManager(
        defaults={"environment": "local", "service_name": "ai-employee"},
        required_keys=["environment", "service_name"],
    )
    observability = ObservabilityManager(service, health, audit)
    deployment = DeploymentValidator(config, health)
    diagnostics = DiagnosticsManager(observability, deployment)
    authorization = LocalAuthorizationManager(
        role_bindings={"system": {"admin"}},
        role_permissions={"admin": {"*"}},
    )
    return EnterpriseOperationsManager(
        authorization,
        audit,
        observability,
        config,
        deployment,
        diagnostics,
        service,
    )


def _experience(service) -> ExperienceIntelligenceManager:
    return ExperienceIntelligenceManager(
        FeedbackManager(),
        ExperienceAnalyzer(service),
        BehaviorAnalyzer(service),
        QualityEvaluator(service),
        FrictionDetector(service),
        RecommendationEngine(),
        ImprovementReporter(),
        service,
    )


def _production(operations) -> ProductionValidationManager:
    return ProductionValidationManager(
        SystemValidator(operations),
        IntegrationValidator(operations),
        PerformanceValidator(operations),
        ReliabilityValidator(operations),
        SecurityValidator(),
        CompatibilityValidator(operations),
        ValidationReporter(),
        operations,
    )


class _Platform:
    """A fully-wired dashboard over shared recording doubles (test convenience)."""

    def __init__(self, components=None) -> None:
        self.operations = _operations(components)
        self.service = self.operations.service
        self.production = _production(self.operations)
        self.experience = _experience(self.service)
        self.manager = DeveloperDashboardManager(
            WorkflowInspector(self.service),
            AgentInspector(self.service),
            MemoryInspector(self.operations),
            SchedulerInspector(self.operations),
            RecoveryInspector(self.operations),
            CapabilityInspector(self.experience),
            ValidationInspector(self.production),
            ExperienceInspector(self.experience),
            OperationsInspector(self.operations),
            DashboardReporter(),
            self.production,
        )

    def submit(self, count: int = 1) -> None:
        for index in range(count):
            self.operations.submit_task(
                _request(request_id=f"r{index}", task_id=f"b{index}")
            )


def _request(request_id="r1", task_id="biz-1"):
    return TaskSubmissionRequest(
        request_id=request_id,
        employee=EmployeeProfile(employee_id="e1", name="Ada"),
        task_id=task_id,
        task="write the report",
        workflow_steps=[WorkflowStep(step_id="s1", capability_name="demo")],
    )


def _degraded(*names) -> dict:
    components = {name: True for name in HEALTH_COMPONENTS}
    for name in names:
        components[name] = False
    return components


# =====================================================================
# Dashboard overview
# =====================================================================
class OverviewTests(unittest.TestCase):
    def test_overview_shape(self):
        platform = _Platform()
        platform.submit(2)
        overview = platform.manager.overview()
        self.assertIsInstance(overview, DashboardOverview)
        self.assertTrue(overview.ready)
        self.assertEqual(overview.state, "HEALTHY")
        self.assertEqual(overview.total_subsystems, 8)
        self.assertEqual(overview.healthy_subsystems, 8)
        self.assertEqual(overview.total_tasks, 2)
        self.assertEqual(overview.active_sessions, 2)
        self.assertEqual(overview.open_issues, 0)

    def test_overview_reflects_feedback(self):
        platform = _Platform()
        platform.experience.record_feedback(rating=5)
        self.assertEqual(platform.manager.overview().feedback_count, 1)

    def test_overview_degraded_not_ready(self):
        platform = _Platform(_degraded("recovery"))
        overview = platform.manager.overview()
        self.assertFalse(overview.ready)
        self.assertGreater(overview.open_issues, 0)


# =====================================================================
# Inspectors
# =====================================================================
class WorkflowInspectorTests(unittest.TestCase):
    def test_history_and_progress(self):
        platform = _Platform()
        platform.submit(3)
        dash = platform.manager.workflow.dashboard()
        self.assertIsInstance(dash, WorkflowDashboard)
        self.assertEqual(dash.total, 3)
        self.assertEqual(dash.status_counts["COMPLETED"], 3)
        self.assertEqual(len(dash.history), 3)
        self.assertEqual(dash.progress["completion_rate"], 1.0)


class AgentInspectorTests(unittest.TestCase):
    def test_registered_agents_and_active_work(self):
        platform = _Platform()
        platform.submit(2)
        dash = platform.manager.agent.dashboard()
        self.assertIsInstance(dash, AgentDashboard)
        self.assertEqual(dash.registered_agents, ["e1"])
        self.assertEqual(dash.agent_count, 1)
        self.assertEqual(dash.active_work, 2)
        self.assertEqual(dash.coordination["tasks"], 2)


class MemoryInspectorTests(unittest.TestCase):
    def test_healthy_memory(self):
        dash = MemoryInspector(_operations()).dashboard()
        self.assertIsInstance(dash, MemoryDashboard)
        self.assertTrue(dash.present)
        self.assertTrue(dash.healthy)
        self.assertEqual(dash.state, "HEALTHY")

    def test_degraded_memory(self):
        dash = MemoryInspector(_operations(_degraded("memory"))).dashboard()
        self.assertFalse(dash.healthy)


class SchedulerInspectorTests(unittest.TestCase):
    def test_queue_summary(self):
        platform = _Platform()
        platform.submit(2)
        dash = platform.manager.scheduler.dashboard()
        self.assertIsInstance(dash, SchedulerDashboard)
        self.assertEqual(dash.scheduled_workflows, 2)
        self.assertEqual(dash.queue_summary["completed"], 2)
        self.assertTrue(dash.healthy)


class RecoveryInspectorTests(unittest.TestCase):
    def test_recovery_history_from_audit(self):
        operations = _operations()
        operations.audit_manager.record_recovery(
            "retry", resource="b1", outcome="recovered"
        )
        dash = RecoveryInspector(operations).dashboard()
        self.assertIsInstance(dash, RecoveryDashboard)
        self.assertEqual(len(dash.recovery_history), 1)
        self.assertEqual(dash.retry_statistics["recovery_events"], 1)

    def test_empty_recovery(self):
        dash = RecoveryInspector(_operations()).dashboard()
        self.assertEqual(dash.recovery_history, [])
        self.assertTrue(dash.healthy)


class CapabilityInspectorTests(unittest.TestCase):
    def test_execution_reflects_tasks(self):
        platform = _Platform()
        platform.submit(2)
        dash = platform.manager.capability.dashboard()
        self.assertIsInstance(dash, CapabilityDashboard)
        self.assertEqual(dash.execution["task_count"], 2)
        self.assertIsInstance(dash.capability_usage, dict)
        self.assertIsInstance(dash.success_rates, dict)


class ValidationInspectorTests(unittest.TestCase):
    def test_ready_platform(self):
        dash = ValidationInspector(_production(_operations())).dashboard()
        self.assertIsInstance(dash, ValidationDashboard)
        self.assertTrue(dash.ready)
        self.assertEqual(dash.passed_validations, 6)
        self.assertEqual(dash.total_validations, 6)
        self.assertEqual(dash.issues, [])
        self.assertEqual(len(dash.results), 6)

    def test_degraded_platform_has_issues(self):
        dash = ValidationInspector(
            _production(_operations(_degraded("recovery")))
        ).dashboard()
        self.assertFalse(dash.ready)
        self.assertTrue(dash.issues)


class ExperienceInspectorTests(unittest.TestCase):
    def test_feedback_and_grade(self):
        service = _service()
        experience = _experience(service)
        experience.record_feedback(rating=4)
        experience.record_feedback(rating=2)
        dash = ExperienceInspector(experience).dashboard()
        self.assertIsInstance(dash, ExperienceDashboard)
        self.assertEqual(dash.feedback_summary["count"], 2)
        self.assertEqual(dash.feedback_summary["average_rating"], 3.0)
        self.assertIn("friction_detected", dash.friction)
        self.assertIn("quality_score", dash.quality)


class OperationsInspectorTests(unittest.TestCase):
    def test_audit_and_status(self):
        operations = _operations()
        operations.submit_task(_request())  # records a TASK audit entry
        dash = OperationsInspector(operations).dashboard()
        self.assertIsInstance(dash, OperationsDashboard)
        self.assertGreaterEqual(dash.audit_summary["total"], 1)
        self.assertTrue(dash.authorization_summary["system_wildcard"])
        self.assertTrue(dash.configuration_status["valid"])
        self.assertTrue(dash.deployment_status["ready"])
        self.assertTrue(dash.diagnostics["healthy"])

    def test_inspector_does_not_mutate_audit(self):
        operations = _operations()
        inspector = OperationsInspector(operations)
        before = len(operations.audit())
        inspector.dashboard()
        inspector.dashboard()
        self.assertEqual(len(operations.audit()), before)


# =====================================================================
# Dashboard reports
# =====================================================================
class ReportTests(unittest.TestCase):
    def setUp(self):
        self.platform = _Platform()
        self.platform.submit(1)

    def test_engineering_dashboard_has_all_sections(self):
        report = self.platform.manager.dashboard()
        self.assertIsInstance(report, DashboardReport)
        self.assertEqual(report.kind, ReportKind.ENGINEERING)
        for section in (
            report.workflow,
            report.agent,
            report.memory,
            report.scheduler,
            report.recovery,
            report.capability,
            report.validation,
            report.experience,
            report.operations,
        ):
            self.assertIsNotNone(section)
        self.assertTrue(report.highlights)

    def test_system_view_subset(self):
        report = self.platform.manager.system_view()
        self.assertEqual(report.kind, ReportKind.SYSTEM)
        self.assertIsNotNone(report.workflow)
        self.assertIsNotNone(report.capability)
        # Health-only sections are omitted from the system view.
        self.assertIsNone(report.validation)
        self.assertIsNone(report.operations)

    def test_health_view_subset(self):
        report = self.platform.manager.health_view()
        self.assertEqual(report.kind, ReportKind.OVERVIEW)
        self.assertIsNotNone(report.validation)
        self.assertIsNotNone(report.operations)
        self.assertIsNone(report.workflow)

    def test_report_routes_by_kind(self):
        for kind in (
            ReportKind.OVERVIEW,
            ReportKind.ENGINEERING,
            ReportKind.SYSTEM,
            ReportKind.DAILY,
        ):
            self.assertEqual(
                self.platform.manager.report(kind).kind, kind
            )

    def test_dashboard_does_not_mutate_state(self):
        operations = self.platform.operations
        before = len(operations.audit())
        self.platform.manager.dashboard()
        self.platform.manager.system_view()
        self.platform.manager.report(ReportKind.DAILY)
        self.assertEqual(len(operations.audit()), before)


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def test_overview_is_frozen(self):
        with self.assertRaises(ValidationError):
            DashboardOverview().ready = True

    def test_section_dtos_are_frozen(self):
        with self.assertRaises(ValidationError):
            WorkflowDashboard().total = 1
        with self.assertRaises(ValidationError):
            AgentDashboard().agent_count = 1
        with self.assertRaises(ValidationError):
            MemoryDashboard().healthy = True
        with self.assertRaises(ValidationError):
            SchedulerDashboard().scheduled_workflows = 1
        with self.assertRaises(ValidationError):
            RecoveryDashboard().present = True
        with self.assertRaises(ValidationError):
            CapabilityDashboard().execution = {}
        with self.assertRaises(ValidationError):
            ValidationDashboard().ready = True
        with self.assertRaises(ValidationError):
            ExperienceDashboard().grade = "x"
        with self.assertRaises(ValidationError):
            OperationsDashboard().audit_summary = {}

    def test_report_is_frozen(self):
        report = DashboardReport(
            report_id="r1",
            kind=ReportKind.OVERVIEW,
            overview=DashboardOverview(),
        )
        with self.assertRaises(ValidationError):
            report.kind = ReportKind.SYSTEM

    def test_report_requires_report_id(self):
        with self.assertRaises(ValidationError):
            DashboardReport(
                report_id="",
                kind=ReportKind.OVERVIEW,
                overview=DashboardOverview(),
            )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_agent_inspector,
            get_capability_inspector,
            get_dashboard_reporter,
            get_experience_inspector,
            get_memory_inspector,
            get_operations_inspector,
            get_recovery_inspector,
            get_scheduler_inspector,
            get_validation_inspector,
            get_workflow_inspector,
        )

        self.assertIsInstance(get_workflow_inspector(), WorkflowInspector)
        self.assertIsInstance(get_agent_inspector(), AgentInspector)
        self.assertIsInstance(get_memory_inspector(), MemoryInspector)
        self.assertIsInstance(get_scheduler_inspector(), SchedulerInspector)
        self.assertIsInstance(get_recovery_inspector(), RecoveryInspector)
        self.assertIsInstance(
            get_capability_inspector(), CapabilityInspector
        )
        self.assertIsInstance(
            get_validation_inspector(), ValidationInspector
        )
        self.assertIsInstance(
            get_experience_inspector(), ExperienceInspector
        )
        self.assertIsInstance(
            get_operations_inspector(), OperationsInspector
        )
        self.assertIsInstance(get_dashboard_reporter(), DashboardReporter)

    def test_manager_provider_wires_collaborators(self):
        from app.core.dependencies import get_developer_dashboard_manager

        manager = get_developer_dashboard_manager()
        self.assertIsInstance(manager, DeveloperDashboardManager)
        self.assertIsInstance(manager.workflow, WorkflowInspector)
        self.assertIsInstance(manager.agent, AgentInspector)
        self.assertIsInstance(manager.memory, MemoryInspector)
        self.assertIsInstance(manager.scheduler, SchedulerInspector)
        self.assertIsInstance(manager.recovery, RecoveryInspector)
        self.assertIsInstance(manager.capability, CapabilityInspector)
        self.assertIsInstance(manager.validation, ValidationInspector)
        self.assertIsInstance(manager.experience, ExperienceInspector)
        self.assertIsInstance(manager.operations, OperationsInspector)
        self.assertIsInstance(manager.reporter, DashboardReporter)
        self.assertIsInstance(
            manager.production, ProductionValidationManager
        )

    def test_manager_provider_shares_state(self):
        from app.core.dependencies import get_developer_dashboard_manager

        manager = get_developer_dashboard_manager()
        # Delegate target and inspectors read one shared platform state.
        self.assertIs(manager.production, manager.validation.production)
        self.assertIs(
            manager.production.operations, manager.operations.operations
        )
        self.assertIs(
            manager.production.operations.service, manager.workflow.service
        )

    def test_manager_provider_uses_injected(self):
        from app.core.dependencies import get_developer_dashboard_manager

        reporter = DashboardReporter()
        manager = get_developer_dashboard_manager(reporter=reporter)
        self.assertIs(manager.reporter, reporter)

    def test_manager_is_read_only_end_to_end(self):
        from app.core.dependencies import get_developer_dashboard_manager

        manager = get_developer_dashboard_manager()
        audit = manager.production.operations.audit_manager
        before = len(audit.history())
        manager.dashboard()
        manager.overview()
        self.assertEqual(len(audit.history()), before)

    def test_manager_holds_only_declared_collaborators(self):
        manager = _Platform().manager
        self.assertEqual(
            set(vars(manager)),
            {
                "workflow",
                "agent",
                "memory",
                "scheduler",
                "recovery",
                "capability",
                "validation",
                "experience",
                "operations",
                "reporter",
                "production",
            },
        )

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            AgentInspectorDep,
            CapabilityInspectorDep,
            DashboardReporterDep,
            DeveloperDashboardManagerDep,
            ExperienceInspectorDep,
            MemoryInspectorDep,
            OperationsInspectorDep,
            RecoveryInspectorDep,
            SchedulerInspectorDep,
            ValidationInspectorDep,
            WorkflowInspectorDep,
        )

        for dep in (
            WorkflowInspectorDep,
            AgentInspectorDep,
            MemoryInspectorDep,
            SchedulerInspectorDep,
            RecoveryInspectorDep,
            CapabilityInspectorDep,
            ValidationInspectorDep,
            ExperienceInspectorDep,
            OperationsInspectorDep,
            DashboardReporterDep,
            DeveloperDashboardManagerDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: prior sprints frozen; no forbidden imports
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_MODULES = {
        "workflow_coordinator",
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
        "repository",
        "fastapi",
        "starlette",
        "sqlalchemy",
        "database",
        "threading",
        "asyncio",
        "socket",
        "requests",
        "httpx",
        "anthropic",
        "openai",
        "boto3",
        "prometheus_client",
        "matplotlib",
        "plotly",
    }

    def test_frozen_1613_production_unchanged(self):
        from app.core.dependencies import get_production_validation_manager

        self.assertIsInstance(
            get_production_validation_manager(),
            ProductionValidationManager,
        )

    def test_frozen_1612_experience_unchanged(self):
        from app.core.dependencies import (
            get_experience_intelligence_manager,
        )

        self.assertIsInstance(
            get_experience_intelligence_manager(),
            ExperienceIntelligenceManager,
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_dashboard_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.dashboard as pkg

        package_dir = os.path.dirname(pkg.__file__)
        offenders = []
        for filename in os.listdir(package_dir):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(package_dir, filename)
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                elif isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                for name in names:
                    tail = name.rsplit(".", 1)[-1]
                    if tail in self._FORBIDDEN_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
