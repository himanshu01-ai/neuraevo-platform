"""Unit + integration tests for the Sprint 16.13 Production Validation Platform.

Exercises the production-validation subsystem: the :class:`SystemValidator`, the
:class:`IntegrationValidator`, the :class:`PerformanceValidator`, the
:class:`ReliabilityValidator`, the :class:`SecurityValidator`, the
:class:`CompatibilityValidator`, the :class:`ValidationReporter`, and the
:class:`ProductionValidationManager` that coordinates them over the frozen Sprint 16.11
:class:`EnterpriseOperationsManager`.

The Production Validation Platform validates only — it never executes a workflow, never
changes AI behaviour, and never modifies an existing service. It reads platform state
only through the operations manager (which here runs over deterministic recording
doubles), and it connects to no load generator, benchmark, penetration test, cloud
validator, container runtime, CI/CD, or external scanner.

Covers, as the sprint requires: system validation, integration validation, performance
summaries, reliability validation, security validation, compatibility validation,
reports, production readiness, DTO immutability, DI wiring, and regression (Sprints
16.1–16.12 unchanged; the validation sub-package imports no Workflow Coordinator,
capability, repository, LLM provider, database, HTTP, or external testing facility).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_production_validation
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import AIEmployee, EmployeeProfile
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
    IntegrationStatus,
    IntegrationValidator,
    PerformanceSummary,
    PerformanceValidator,
    ProductionReadiness,
    ProductionValidationManager,
    ReliabilitySummary,
    ReliabilityValidator,
    SecurityValidator,
    SystemStatus,
    SystemValidator,
    ValidationIssue,
    ValidationReport,
    ValidationReporter,
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
    ValidationStatus,
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


def _manager(components=None) -> ProductionValidationManager:
    operations = _operations(components)
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


def _degraded(*names) -> dict:
    """A health map with ``names`` marked unavailable."""
    components = {name: True for name in HEALTH_COMPONENTS}
    for name in names:
        components[name] = False
    return components


def _request(request_id="r1", task_id="biz-1"):
    return TaskSubmissionRequest(
        request_id=request_id,
        employee=EmployeeProfile(employee_id="e1", name="Ada"),
        task_id=task_id,
        task="write the report",
        workflow_steps=[WorkflowStep(step_id="s1", capability_name="demo")],
    )


# =====================================================================
# System validation
# =====================================================================
class SystemValidationTests(unittest.TestCase):
    def test_all_subsystems_present(self):
        statuses = SystemValidator(_operations()).system_statuses()
        names = [s.name for s in statuses]
        self.assertEqual(
            names,
            [
                "planning",
                "runtime",
                "capabilities",
                "ai_employee",
                "memory",
                "scheduler",
                "recovery",
                "operations",
            ],
        )
        self.assertTrue(all(isinstance(s, SystemStatus) for s in statuses))
        self.assertTrue(all(s.present for s in statuses))

    def test_healthy_platform_passes(self):
        result = SystemValidator(_operations()).validate()
        self.assertIsInstance(result, ValidationResult)
        self.assertEqual(result.status, ValidationStatus.PASSED)
        self.assertTrue(result.passed)

    def test_degraded_subsystem_fails(self):
        result = SystemValidator(_operations(_degraded("ai_employee"))).validate()
        self.assertEqual(result.status, ValidationStatus.FAILED)
        self.assertFalse(result.passed)
        self.assertTrue(
            any(i.component == "ai_employee" for i in result.issues)
        )

    def test_capabilities_track_runtime(self):
        statuses = {
            s.name: s
            for s in SystemValidator(
                _operations(_degraded("runtime"))
            ).system_statuses()
        }
        self.assertFalse(statuses["capabilities"].healthy)


# =====================================================================
# Integration validation
# =====================================================================
class IntegrationValidationTests(unittest.TestCase):
    def test_all_points_reported(self):
        statuses = IntegrationValidator(_operations()).integration_statuses()
        self.assertEqual(len(statuses), 7)
        self.assertTrue(all(isinstance(s, IntegrationStatus) for s in statuses))
        self.assertTrue(all(s.connected for s in statuses))

    def test_healthy_platform_passes(self):
        result = IntegrationValidator(_operations()).validate()
        self.assertEqual(result.status, ValidationStatus.PASSED)

    def test_service_operations_shared_instance(self):
        statuses = {
            s.name: s
            for s in IntegrationValidator(_operations()).integration_statuses()
        }
        self.assertTrue(statuses["Service <-> Operations"].consistent)

    def test_unhealthy_side_warns_not_blocks(self):
        result = IntegrationValidator(_operations(_degraded("memory"))).validate()
        # Wiring is intact; a down subsystem is a non-blocking warning.
        self.assertEqual(result.status, ValidationStatus.WARNING)
        self.assertTrue(result.passed)

    def test_approval_notification_integrated(self):
        statuses = {
            s.name: s
            for s in IntegrationValidator(_operations()).integration_statuses()
        }
        self.assertTrue(statuses["Approval <-> Notification"].connected)


# =====================================================================
# Performance summaries
# =====================================================================
class PerformanceValidationTests(unittest.TestCase):
    def test_summary_shape(self):
        operations = _operations()
        operations.submit_task(_request(task_id="b1"))
        operations.submit_task(_request(request_id="r2", task_id="b2"))
        summary = PerformanceValidator(operations).summary()
        self.assertIsInstance(summary, PerformanceSummary)
        self.assertEqual(summary.throughput["tasks_total"], 2)
        self.assertEqual(summary.throughput["tasks_completed"], 2)
        self.assertEqual(summary.response["success_rate"], 1.0)
        self.assertEqual(summary.resource_usage["sessions_total"], 2)

    def test_response_statistics_empty(self):
        stats = PerformanceValidator(_operations()).response_statistics()
        self.assertEqual(stats["success_rate"], 0.0)
        self.assertEqual(stats["failure_rate"], 0.0)

    def test_validate_passes(self):
        result = PerformanceValidator(_operations()).validate()
        self.assertEqual(result.scope, ValidationScope.PERFORMANCE)
        self.assertTrue(result.passed)

    def test_no_timers_used(self):
        # Throughput is a processed-work count, not a per-second rate.
        operations = _operations()
        operations.submit_task(_request())
        throughput = PerformanceValidator(operations).throughput_summary()
        self.assertEqual(set(throughput), {
            "tasks_total", "tasks_completed", "tasks_failed", "tasks_cancelled"
        })


# =====================================================================
# Reliability validation
# =====================================================================
class ReliabilityValidationTests(unittest.TestCase):
    def test_healthy_platform_is_reliable(self):
        summary = ReliabilityValidator(_operations()).summary()
        self.assertIsInstance(summary, ReliabilitySummary)
        self.assertTrue(summary.reliable)
        self.assertTrue(summary.deterministic)
        self.assertTrue(summary.workflow_consistent)

    def test_workflow_consistency_with_tasks(self):
        operations = _operations()
        operations.submit_task(_request())
        summary = ReliabilityValidator(operations).summary()
        self.assertTrue(summary.workflow_consistent)
        self.assertTrue(summary.state_consistent)

    def test_recovery_down_fails(self):
        result = ReliabilityValidator(_operations(_degraded("recovery"))).validate()
        self.assertEqual(result.status, ValidationStatus.FAILED)
        self.assertFalse(result.passed)
        self.assertTrue(
            any(i.component == "recovery_ready" for i in result.issues)
        )

    def test_determinism_check(self):
        self.assertTrue(ReliabilityValidator(_operations())._deterministic())


# =====================================================================
# Security validation
# =====================================================================
class SecurityValidationTests(unittest.TestCase):
    def setUp(self):
        self.validator = SecurityValidator()

    def test_no_forbidden_imports(self):
        self.assertEqual(self.validator.forbidden_import_offenders(), [])

    def test_provider_isolation(self):
        self.assertTrue(self.validator.provider_isolation_ok())

    def test_all_dtos_frozen(self):
        self.assertEqual(self.validator.mutable_dto_offenders(), [])

    def test_validate_passes(self):
        result = self.validator.validate()
        self.assertEqual(result.scope, ValidationScope.SECURITY)
        self.assertTrue(result.passed)
        self.assertTrue(result.result_metadata["provider_isolation"])


# =====================================================================
# Compatibility validation
# =====================================================================
class CompatibilityValidationTests(unittest.TestCase):
    def test_healthy_platform_passes(self):
        result = CompatibilityValidator(_operations()).validate()
        self.assertEqual(result.scope, ValidationScope.COMPATIBILITY)
        self.assertTrue(result.passed)

    def test_di_graph_detects_missing_collaborator(self):
        operations = _operations()
        operations.audit_manager = None  # break the DI graph
        result = CompatibilityValidator(operations).validate()
        self.assertFalse(result.passed)
        self.assertTrue(
            any(i.component == "di-graph" for i in result.issues)
        )

    def test_shared_service_invariant(self):
        operations = _operations()
        # Both the operations manager and its observability share one service.
        self.assertIs(operations.service, operations.observability.service)
        self.assertTrue(
            CompatibilityValidator(operations).validate().passed
        )


# =====================================================================
# Reports
# =====================================================================
class ReportTests(unittest.TestCase):
    def setUp(self):
        self.reporter = ValidationReporter()
        self.manager = _manager()

    def test_scoped_reports(self):
        system = self.reporter.system_report(self.manager.system.validate())
        self.assertIsInstance(system, ValidationReport)
        self.assertEqual(system.scope, ValidationScope.SYSTEM)
        self.assertEqual(system.report_id, "validation-system")

    def test_final_report_bundles_all(self):
        report = self.manager.full_validation()
        self.assertEqual(report.scope, ValidationScope.FINAL)
        self.assertEqual(len(report.results), 6)
        self.assertTrue(report.passed)

    def test_readiness_report(self):
        report = self.reporter.readiness_report(self.manager.readiness())
        self.assertEqual(report.scope, ValidationScope.READINESS)
        self.assertTrue(report.passed)

    def test_report_routes_by_scope(self):
        for scope in (
            ValidationScope.SYSTEM,
            ValidationScope.INTEGRATION,
            ValidationScope.PERFORMANCE,
            ValidationScope.RELIABILITY,
            ValidationScope.SECURITY,
            ValidationScope.COMPATIBILITY,
            ValidationScope.READINESS,
            ValidationScope.FINAL,
        ):
            self.assertEqual(self.manager.report(scope).scope, scope)


# =====================================================================
# Production readiness + manager coordination
# =====================================================================
class ReadinessTests(unittest.TestCase):
    def test_healthy_platform_ready(self):
        readiness = _manager().readiness()
        self.assertIsInstance(readiness, ProductionReadiness)
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.passed_validations, 6)
        self.assertEqual(readiness.total_validations, 6)
        self.assertEqual(readiness.blocking_issues, [])
        self.assertEqual(len(readiness.results), 6)

    def test_degraded_platform_not_ready(self):
        readiness = _manager(_degraded("recovery")).readiness()
        self.assertFalse(readiness.ready)
        self.assertTrue(readiness.blocking_issues)

    def test_summary_is_compact(self):
        summary = _manager().summary()
        self.assertIsInstance(summary, ProductionReadiness)
        self.assertEqual(summary.results, [])  # compact: no per-scope results
        self.assertTrue(summary.ready)

    def test_validate_returns_six_results(self):
        results = _manager().validate()
        self.assertEqual(len(results), 6)
        self.assertTrue(all(isinstance(r, ValidationResult) for r in results))
        scopes = {r.scope for r in results}
        self.assertEqual(
            scopes,
            {
                ValidationScope.SYSTEM,
                ValidationScope.INTEGRATION,
                ValidationScope.PERFORMANCE,
                ValidationScope.RELIABILITY,
                ValidationScope.SECURITY,
                ValidationScope.COMPATIBILITY,
            },
        )

    def test_manager_holds_only_declared_collaborators(self):
        manager = _manager()
        self.assertEqual(
            set(vars(manager)),
            {
                "system",
                "integration",
                "performance",
                "reliability",
                "security",
                "compatibility",
                "reporter",
                "operations",
            },
        )

    def test_readiness_state_from_operations(self):
        readiness = _manager().readiness()
        self.assertEqual(
            readiness.state, _operations().system_status().state
        )


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def test_validation_result_is_frozen(self):
        result = ValidationResult(
            name="n", scope=ValidationScope.SYSTEM,
            status=ValidationStatus.PASSED,
        )
        with self.assertRaises(ValidationError):
            result.passed = True

    def test_validation_issue_is_frozen(self):
        issue = ValidationIssue(
            issue_id="i1", severity=ValidationSeverity.ERROR, message="m"
        )
        with self.assertRaises(ValidationError):
            issue.message = "x"

    def test_reports_and_statuses_frozen(self):
        with self.assertRaises(ValidationError):
            ValidationReport(
                report_id="r1", scope=ValidationScope.FINAL
            ).passed = True
        with self.assertRaises(ValidationError):
            SystemStatus(name="planning").healthy = True
        with self.assertRaises(ValidationError):
            IntegrationStatus(name="a<->b").connected = True

    def test_summaries_and_readiness_frozen(self):
        with self.assertRaises(ValidationError):
            PerformanceSummary().execution = {}
        with self.assertRaises(ValidationError):
            ReliabilitySummary().reliable = True
        with self.assertRaises(ValidationError):
            ProductionReadiness().ready = True

    def test_issue_requires_non_empty_message(self):
        with self.assertRaises(ValidationError):
            ValidationIssue(
                issue_id="i1", severity=ValidationSeverity.INFO, message=""
            )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_compatibility_validator,
            get_integration_validator,
            get_performance_validator,
            get_reliability_validator,
            get_security_validator,
            get_system_validator,
            get_validation_reporter,
        )

        self.assertIsInstance(get_system_validator(), SystemValidator)
        self.assertIsInstance(
            get_integration_validator(), IntegrationValidator
        )
        self.assertIsInstance(
            get_performance_validator(), PerformanceValidator
        )
        self.assertIsInstance(
            get_reliability_validator(), ReliabilityValidator
        )
        self.assertIsInstance(get_security_validator(), SecurityValidator)
        self.assertIsInstance(
            get_compatibility_validator(), CompatibilityValidator
        )
        self.assertIsInstance(
            get_validation_reporter(), ValidationReporter
        )

    def test_manager_provider_wires_collaborators(self):
        from app.core.dependencies import get_production_validation_manager

        manager = get_production_validation_manager()
        self.assertIsInstance(manager, ProductionValidationManager)
        self.assertIsInstance(manager.system, SystemValidator)
        self.assertIsInstance(manager.integration, IntegrationValidator)
        self.assertIsInstance(manager.performance, PerformanceValidator)
        self.assertIsInstance(manager.reliability, ReliabilityValidator)
        self.assertIsInstance(manager.security, SecurityValidator)
        self.assertIsInstance(manager.compatibility, CompatibilityValidator)
        self.assertIsInstance(manager.reporter, ValidationReporter)
        self.assertIsInstance(
            manager.operations, EnterpriseOperationsManager
        )

    def test_manager_provider_shares_operations(self):
        from app.core.dependencies import get_production_validation_manager

        manager = get_production_validation_manager()
        # Every operations-backed validator must read the same platform state.
        self.assertIs(manager.operations, manager.system.operations)
        self.assertIs(manager.operations, manager.integration.operations)
        self.assertIs(manager.operations, manager.reliability.operations)

    def test_manager_provider_uses_injected(self):
        from app.core.dependencies import get_production_validation_manager

        reporter = ValidationReporter()
        manager = get_production_validation_manager(reporter=reporter)
        self.assertIs(manager.reporter, reporter)

    def test_manager_provider_is_production_ready(self):
        from app.core.dependencies import get_production_validation_manager

        # The fully-wired production platform validates itself as ready.
        self.assertTrue(get_production_validation_manager().readiness().ready)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            CompatibilityValidatorDep,
            IntegrationValidatorDep,
            PerformanceValidatorDep,
            ProductionValidationManagerDep,
            ReliabilityValidatorDep,
            SecurityValidatorDep,
            SystemValidatorDep,
            ValidationReporterDep,
        )

        for dep in (
            SystemValidatorDep,
            IntegrationValidatorDep,
            PerformanceValidatorDep,
            ReliabilityValidatorDep,
            SecurityValidatorDep,
            CompatibilityValidatorDep,
            ValidationReporterDep,
            ProductionValidationManagerDep,
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
        "sklearn",
        "tensorflow",
        "torch",
    }

    def test_frozen_1612_experience_unchanged(self):
        from app.core.dependencies import (
            get_experience_intelligence_manager,
        )
        from app.services.ai_employee.experience import (
            ExperienceIntelligenceManager,
        )

        self.assertIsInstance(
            get_experience_intelligence_manager(),
            ExperienceIntelligenceManager,
        )

    def test_frozen_1611_operations_unchanged(self):
        from app.core.dependencies import (
            get_enterprise_operations_manager,
        )

        self.assertIsInstance(
            get_enterprise_operations_manager(), EnterpriseOperationsManager
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_validation_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.validation as pkg

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
