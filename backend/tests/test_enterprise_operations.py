"""Unit + integration tests for the Sprint 16.11 Enterprise Operations Layer.

Exercises the operations subsystem: the :class:`LocalAuthorizationManager`, the
:class:`AuditManager`, the :class:`ObservabilityManager`, the
:class:`ConfigurationManager`, the :class:`DeploymentValidator`, the
:class:`DiagnosticsManager`, and the :class:`EnterpriseOperationsManager` that
coordinates them over the frozen Sprint 16.10 :class:`AIEmployeeService`.

The Enterprise Operations Layer adds operational capabilities only — it adds no
business functionality, modifies no workflow execution, and modifies no AI
behaviour. Every business request is delegated to the :class:`AIEmployeeService`
(which here runs over deterministic recording doubles), and the layer connects to no
identity provider, cloud SDK, external monitor, HTTP transport, or database.

Covers, as the sprint requires: authorization, audit logging, audit queries,
metrics, component status, configuration validation, deployment validation,
diagnostics, enterprise status, service delegation, DTO immutability, DI wiring, and
regression (Sprints 16.1–16.10 unchanged; the operations sub-package imports no
Workflow Coordinator, capability, repository, LLM provider, database, HTTP, auth
provider, cloud SDK, or external monitoring facility).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_enterprise_operations
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import AIEmployee, EmployeeProfile
from app.services.ai_employee.operations import (
    AuditCategory,
    AuditManager,
    AuditQuery,
    AuditRecord,
    AuthorizationDecision,
    AuthorizationManager,
    AuthorizationResult,
    CheckStatus,
    ComponentStatus,
    ConfigurationManager,
    ConfigurationReport,
    DeploymentReport,
    DeploymentValidator,
    DiagnosticsManager,
    DiagnosticsReport,
    EnterpriseOperationsManager,
    EnterpriseStatus,
    LocalAuthorizationManager,
    MetricSnapshot,
    ObservabilityManager,
)
from app.services.ai_employee.service import (
    AIEmployeeService,
    ErrorMapper,
    HealthManager,
    HealthState,
    IdempotencyManager,
    RequestValidator,
    ResponseBuilder,
    SessionManager,
    TaskSubmissionRequest,
)
from app.services.ai_employee.service.health import HEALTH_COMPONENTS
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
        self.calls = []

    def execute(
        self,
        steps,
        workflow_id="workflow",
        runtime_id="",
        execution_id="",
        initial_inputs=None,
    ) -> WorkflowExecutionResult:
        self.calls.append({"steps": steps})
        return WorkflowExecutionResult(
            workflow_id=workflow_id,
            workflow_status=self._status,
            total_step_count=len(steps),
        )


def _service(status: str = _COMPLETED, components=None):
    ai = AIEmployee(_RecordingPlanningEngine(), _RecordingWorkflowCoordinator(status))
    health = HealthManager(
        components or {name: True for name in HEALTH_COMPONENTS}
    )
    service = AIEmployeeService(
        ai,
        SessionManager(),
        RequestValidator(),
        ResponseBuilder(),
        IdempotencyManager(),
        health,
        ErrorMapper(),
    )
    return service, health


def _authz():
    return LocalAuthorizationManager(
        role_bindings={"system": {"admin"}, "alice": {"operator"}},
        role_permissions={"admin": {"*"}, "operator": {"task.read"}},
        action_permissions={
            "task.submit": "task.write",
            "task.read": "task.read",
        },
    )


def _operations(status: str = _COMPLETED, components=None, authz=None):
    service, health = _service(status, components)
    audit = AuditManager()
    config = ConfigurationManager(
        defaults={"environment": "local", "service_name": "ai-employee"},
        required_keys=["environment", "service_name"],
    )
    observability = ObservabilityManager(service, health, audit)
    deployment = DeploymentValidator(config, health)
    diagnostics = DiagnosticsManager(observability, deployment)
    manager = EnterpriseOperationsManager(
        authz or _authz(),
        audit,
        observability,
        config,
        deployment,
        diagnostics,
        service,
    )
    return manager, service


def _request(request_id="r1", task_id="biz-1"):
    return TaskSubmissionRequest(
        request_id=request_id,
        employee=EmployeeProfile(employee_id="e1", name="Ada"),
        task_id=task_id,
        task="write the report",
        workflow_steps=[WorkflowStep(step_id="s1", capability_name="demo")],
    )


# =====================================================================
# Authorization
# =====================================================================
class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.authz = _authz()

    def test_is_authorization_manager(self):
        self.assertIsInstance(self.authz, AuthorizationManager)

    def test_wildcard_allows_everything(self):
        result = self.authz.authorize("system", "task.submit", "biz-1")
        self.assertIsInstance(result, AuthorizationResult)
        self.assertTrue(result.allowed)
        self.assertEqual(result.decision, AuthorizationDecision.ALLOW)

    def test_permission_required_denies_without_it(self):
        result = self.authz.authorize("alice", "task.submit")
        self.assertFalse(result.allowed)
        self.assertEqual(result.decision, AuthorizationDecision.DENY)

    def test_permission_required_allows_with_it(self):
        self.assertTrue(self.authz.authorize("alice", "task.read").allowed)

    def test_unmapped_action_defaults_deny(self):
        self.assertFalse(self.authz.authorize("alice", "unknown.action").allowed)

    def test_unmapped_action_default_allow(self):
        permissive = LocalAuthorizationManager(default_allow=True)
        self.assertTrue(permissive.authorize("anyone", "whatever").allowed)

    def test_validate_permission(self):
        self.assertTrue(self.authz.validate_permission("alice", "task.read"))
        self.assertFalse(self.authz.validate_permission("alice", "task.write"))
        self.assertTrue(
            self.authz.validate_permission("system", "anything")
        )  # wildcard

    def test_validate_role(self):
        self.assertTrue(self.authz.validate_role("alice", "operator"))
        self.assertFalse(self.authz.validate_role("alice", "admin"))

    def test_manager_authorize_is_audited(self):
        manager, _ = _operations()
        manager.authorize("system", "task.submit", "biz-1")
        records = manager.audit()
        self.assertTrue(
            any(
                r.action == "authorize:task.submit"
                and r.category == AuditCategory.ADMINISTRATIVE
                for r in records
            )
        )


# =====================================================================
# Audit logging
# =====================================================================
class AuditLoggingTests(unittest.TestCase):
    def setUp(self):
        self.audit = AuditManager()

    def test_record_appends_immutable_record(self):
        record = self.audit.record(
            AuditCategory.TASK, "submit", resource="biz-1", outcome="ok"
        )
        self.assertIsInstance(record, AuditRecord)
        self.assertEqual(record.category, AuditCategory.TASK)
        self.assertEqual(len(self.audit.history()), 1)

    def test_sequence_is_monotonic(self):
        first = self.audit.record(AuditCategory.TASK, "a")
        second = self.audit.record(AuditCategory.TASK, "b")
        self.assertEqual(second.sequence, first.sequence + 1)

    def test_category_helpers(self):
        self.audit.record_task("t")
        self.audit.record_workflow("w")
        self.audit.record_approval("ap")
        self.audit.record_recovery("rec")
        self.audit.record_administrative("adm")
        categories = {r.category for r in self.audit.history()}
        self.assertEqual(
            categories,
            {
                AuditCategory.TASK,
                AuditCategory.WORKFLOW,
                AuditCategory.APPROVAL,
                AuditCategory.RECOVERY,
                AuditCategory.ADMINISTRATIVE,
            },
        )

    def test_history_is_a_copy(self):
        self.audit.record_task("t")
        history = self.audit.history()
        history.clear()
        self.assertEqual(len(self.audit.history()), 1)  # unaffected


# =====================================================================
# Audit queries
# =====================================================================
class AuditQueryTests(unittest.TestCase):
    def setUp(self):
        self.audit = AuditManager()
        self.audit.record_task("submit", principal="alice", resource="biz-1")
        self.audit.record_workflow("run", principal="bob", resource="wf-1")
        self.audit.record_task("cancel", principal="alice", resource="biz-2")

    def test_search_matches_substring(self):
        self.assertEqual(len(self.audit.search("alice")), 2)
        self.assertEqual(len(self.audit.search("wf-1")), 1)
        self.assertEqual(len(self.audit.search("nothing")), 0)

    def test_filter_by_category(self):
        results = self.audit.filter(AuditQuery(category=AuditCategory.TASK))
        self.assertEqual(len(results), 2)

    def test_filter_by_principal_and_action(self):
        results = self.audit.filter(
            AuditQuery(principal="alice", action="submit")
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].resource, "biz-1")

    def test_filter_by_text_and_limit(self):
        results = self.audit.filter(AuditQuery(text="alice", limit=1))
        self.assertEqual(len(results), 1)

    def test_filter_no_criteria_returns_all(self):
        self.assertEqual(len(self.audit.filter(AuditQuery())), 3)


# =====================================================================
# Observability: metrics / component status / statistics
# =====================================================================
class ObservabilityTests(unittest.TestCase):
    def test_metrics_count_tasks_and_sessions(self):
        manager, service = _operations()
        service.submit_task(_request(task_id="b1"))
        service.submit_task(_request(request_id="r2", task_id="b2"))
        metrics = manager.observability.metrics()
        self.assertIsInstance(metrics, MetricSnapshot)
        self.assertEqual(metrics.metrics["tasks_total"], 2)
        self.assertEqual(metrics.metrics["tasks_completed"], 2)
        self.assertEqual(metrics.metrics["sessions_total"], 2)

    def test_execution_statistics(self):
        manager, service = _operations()
        service.submit_task(_request())
        stats = manager.observability.execution_statistics()
        self.assertEqual(stats.name, "execution")
        self.assertEqual(stats.metrics["tasks_completed"], 1)

    def test_service_statistics(self):
        manager, service = _operations()
        service.submit_task(_request())
        stats = manager.observability.service_statistics()
        self.assertEqual(stats.name, "service")
        self.assertEqual(stats.metrics["sessions_total"], 1)

    def test_component_status_projects_health(self):
        manager, _ = _operations()
        statuses = manager.observability.component_status()
        self.assertEqual(len(statuses), len(HEALTH_COMPONENTS))
        self.assertTrue(all(isinstance(s, ComponentStatus) for s in statuses))
        self.assertTrue(all(s.healthy for s in statuses))

    def test_component_status_reflects_unhealthy(self):
        components = {name: True for name in HEALTH_COMPONENTS}
        components["memory"] = False
        manager, _ = _operations(components=components)
        by_name = {s.name: s for s in manager.observability.component_status()}
        self.assertFalse(by_name["memory"].healthy)
        self.assertEqual(by_name["memory"].state, HealthState.UNHEALTHY)


# =====================================================================
# Configuration validation
# =====================================================================
class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config = ConfigurationManager(
            defaults={"environment": "local", "service_name": "svc"},
            required_keys=["environment", "service_name"],
        )

    def test_load_merges_overrides(self):
        loaded = self.config.load({"environment": "prod"})
        self.assertEqual(loaded["environment"], "prod")
        self.assertEqual(loaded["service_name"], "svc")

    def test_validate_valid_configuration(self):
        report = self.config.validate(self.config.load())
        self.assertIsInstance(report, ConfigurationReport)
        self.assertTrue(report.valid)
        self.assertEqual(report.issues, [])

    def test_validate_missing_required(self):
        report = self.config.validate({"environment": "local"})
        self.assertFalse(report.valid)
        self.assertTrue(
            any("service_name" in issue for issue in report.issues)
        )

    def test_validate_empty_required(self):
        report = self.config.validate(
            {"environment": "", "service_name": "svc"}
        )
        self.assertFalse(report.valid)

    def test_validate_unknown_key_warns(self):
        report = self.config.validate(
            {"environment": "local", "service_name": "svc", "extra": 1}
        )
        self.assertTrue(report.valid)
        self.assertTrue(any("extra" in w for w in report.warnings))

    def test_export_is_sorted(self):
        exported = self.config.export({"b": 2, "a": 1})
        self.assertEqual(list(exported.keys()), ["a", "b"])


# =====================================================================
# Deployment validation
# =====================================================================
class DeploymentTests(unittest.TestCase):
    def _validator(self, components=None):
        health = HealthManager(
            components or {name: True for name in HEALTH_COMPONENTS}
        )
        config = ConfigurationManager(
            defaults={"environment": "local", "service_name": "svc"},
            required_keys=["environment", "service_name"],
        )
        return DeploymentValidator(config, health), config

    def test_validate_dependencies_all_ready(self):
        validator, _ = self._validator()
        report = validator.validate_dependencies()
        self.assertIsInstance(report, DeploymentReport)
        self.assertTrue(report.ready)
        self.assertTrue(
            all(v == CheckStatus.PASS.value for v in report.checks.values())
        )

    def test_validate_dependencies_detects_unhealthy(self):
        components = {name: True for name in HEALTH_COMPONENTS}
        components["scheduler"] = False
        validator, _ = self._validator(components)
        report = validator.validate_dependencies()
        self.assertFalse(report.ready)
        self.assertEqual(
            report.checks["scheduler"], CheckStatus.FAIL.value
        )

    def test_validate_components(self):
        validator, _ = self._validator()
        self.assertTrue(validator.validate_components().ready)

    def test_validate_configuration(self):
        validator, config = self._validator()
        ok = validator.validate_configuration(config.load())
        self.assertTrue(ok.ready)
        bad = validator.validate_configuration({"environment": "local"})
        self.assertFalse(bad.ready)

    def test_validate_startup_aggregates(self):
        validator, config = self._validator()
        report = validator.validate_startup(config.load())
        self.assertTrue(report.ready)
        self.assertEqual(report.detail, "startup")
        # Aggregated checks are namespaced by scope.
        self.assertTrue(
            any(k.startswith("dependency:") for k in report.checks)
        )
        self.assertTrue(
            any(k.startswith("component:") for k in report.checks)
        )
        self.assertIn("configuration", report.checks)

    def test_validate_startup_not_ready_on_bad_config(self):
        validator, _ = self._validator()
        report = validator.validate_startup({"environment": "local"})
        self.assertFalse(report.ready)


# =====================================================================
# Diagnostics
# =====================================================================
class DiagnosticsTests(unittest.TestCase):
    def test_diagnostics_healthy(self):
        manager, _ = _operations()
        report = manager.diagnostics()
        self.assertIsInstance(report, DiagnosticsReport)
        self.assertTrue(report.healthy)
        self.assertEqual(len(report.components), len(HEALTH_COMPONENTS))

    def test_diagnostics_reports_issues(self):
        components = {name: True for name in HEALTH_COMPONENTS}
        components["recovery"] = False
        manager, _ = _operations(components=components)
        report = manager.diagnostics()
        self.assertFalse(report.healthy)
        self.assertTrue(report.issues)

    def test_health_summary(self):
        manager, _ = _operations()
        report = manager.diagnostics_manager.health_summary()
        self.assertTrue(report.healthy)
        self.assertIn("healthy", report.summary)

    def test_dependency_report(self):
        manager, _ = _operations()
        report = manager.diagnostics_manager.dependency_report()
        self.assertTrue(report.healthy)
        self.assertEqual(len(report.dependencies), len(HEALTH_COMPONENTS))

    def test_system_report_includes_metrics(self):
        manager, _ = _operations()
        report = manager.system_report()
        self.assertIsNotNone(report.metrics)
        self.assertTrue(report.components)
        self.assertTrue(report.dependencies)


# =====================================================================
# Enterprise status + environment validation (manager)
# =====================================================================
class EnterpriseStatusTests(unittest.TestCase):
    def test_status_healthy(self):
        manager, _ = _operations()
        status = manager.system_status()
        self.assertIsInstance(status, EnterpriseStatus)
        self.assertEqual(status.state, HealthState.HEALTHY)
        self.assertTrue(status.ready)
        self.assertIsNotNone(status.metrics)

    def test_status_degraded(self):
        components = {name: True for name in HEALTH_COMPONENTS}
        components["memory"] = False
        manager, _ = _operations(components=components)
        status = manager.system_status()
        self.assertEqual(status.state, HealthState.DEGRADED)
        self.assertFalse(status.ready)

    def test_status_unhealthy(self):
        components = {name: False for name in HEALTH_COMPONENTS}
        manager, _ = _operations(components=components)
        self.assertEqual(
            manager.system_status().state, HealthState.UNHEALTHY
        )

    def test_status_counts_audit_records(self):
        manager, _ = _operations()
        manager.authorize("system", "task.submit")
        status = manager.system_status()
        self.assertGreaterEqual(status.audit_record_count, 1)

    def test_validate_environment_ready_and_audited(self):
        manager, _ = _operations()
        report = manager.validate_environment()
        self.assertTrue(report.ready)
        self.assertTrue(
            any(
                r.action == "validate_environment" for r in manager.audit()
            )
        )

    def test_validate_configuration_uses_defaults(self):
        manager, _ = _operations()
        self.assertTrue(manager.validate_configuration().valid)


# =====================================================================
# Service delegation
# =====================================================================
class ServiceDelegationTests(unittest.TestCase):
    def test_submit_task_delegates_to_service(self):
        manager, service = _operations()
        response = manager.submit_task(_request())
        self.assertTrue(response.accepted)
        # The task landed in the service's registry (delegation, not local run).
        self.assertEqual(len(service.list_tasks()), 1)

    def test_submit_task_is_audited(self):
        manager, _ = _operations()
        manager.submit_task(_request(task_id="biz-9"))
        self.assertTrue(
            any(
                r.category == AuditCategory.TASK
                and r.action == "submit_task"
                and r.resource == "biz-9"
                for r in manager.audit()
            )
        )

    def test_manager_holds_only_declared_collaborators(self):
        manager, _ = _operations()
        self.assertEqual(
            set(vars(manager)),
            {
                "authorization",
                "audit_manager",
                "observability",
                "configuration",
                "deployment",
                "diagnostics_manager",
                "service",
            },
        )


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def test_authorization_result_is_frozen(self):
        result = AuthorizationResult(
            allowed=True, decision=AuthorizationDecision.ALLOW
        )
        with self.assertRaises(ValidationError):
            result.allowed = False

    def test_audit_record_is_frozen(self):
        record = AuditRecord(
            record_id="a1", category=AuditCategory.TASK, action="x"
        )
        with self.assertRaises(ValidationError):
            record.action = "y"

    def test_audit_query_is_frozen(self):
        with self.assertRaises(ValidationError):
            AuditQuery(limit=5).limit = 9

    def test_metric_snapshot_is_frozen(self):
        with self.assertRaises(ValidationError):
            MetricSnapshot(name="m").name = "n"

    def test_component_status_is_frozen(self):
        status = ComponentStatus(name="planning", state=HealthState.HEALTHY)
        with self.assertRaises(ValidationError):
            status.healthy = True

    def test_reports_are_frozen(self):
        with self.assertRaises(ValidationError):
            ConfigurationReport(valid=True).valid = False
        with self.assertRaises(ValidationError):
            DeploymentReport(ready=True).ready = False
        with self.assertRaises(ValidationError):
            DiagnosticsReport(healthy=True).healthy = False

    def test_enterprise_status_is_frozen(self):
        with self.assertRaises(ValidationError):
            EnterpriseStatus(state=HealthState.HEALTHY).ready = True

    def test_audit_record_requires_non_empty_action(self):
        with self.assertRaises(ValidationError):
            AuditRecord(record_id="a1", category=AuditCategory.TASK, action="")


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_audit_manager,
            get_authorization_manager,
            get_configuration_manager,
            get_deployment_validator,
            get_diagnostics_manager,
            get_observability_manager,
        )

        self.assertIsInstance(
            get_authorization_manager(), LocalAuthorizationManager
        )
        self.assertIsInstance(get_audit_manager(), AuditManager)
        self.assertIsInstance(
            get_configuration_manager(), ConfigurationManager
        )
        self.assertIsInstance(
            get_observability_manager(), ObservabilityManager
        )
        self.assertIsInstance(
            get_deployment_validator(), DeploymentValidator
        )
        self.assertIsInstance(
            get_diagnostics_manager(), DiagnosticsManager
        )

    def test_manager_provider_wires_collaborators(self):
        from app.core.dependencies import get_enterprise_operations_manager

        manager = get_enterprise_operations_manager()
        self.assertIsInstance(manager, EnterpriseOperationsManager)
        self.assertIsInstance(manager.authorization, AuthorizationManager)
        self.assertIsInstance(manager.audit_manager, AuditManager)
        self.assertIsInstance(manager.observability, ObservabilityManager)
        self.assertIsInstance(manager.configuration, ConfigurationManager)
        self.assertIsInstance(manager.deployment, DeploymentValidator)
        self.assertIsInstance(
            manager.diagnostics_manager, DiagnosticsManager
        )
        self.assertIsInstance(manager.service, AIEmployeeService)

    def test_manager_provider_shares_instances(self):
        from app.core.dependencies import get_enterprise_operations_manager

        manager = get_enterprise_operations_manager()
        # Telemetry + audit must be consistent: shared service and audit ledger.
        self.assertIs(manager.service, manager.observability.service)
        self.assertIs(
            manager.audit_manager, manager.observability.audit_manager
        )

    def test_manager_provider_uses_injected(self):
        from app.core.dependencies import get_enterprise_operations_manager

        audit = AuditManager()
        manager = get_enterprise_operations_manager(audit=audit)
        self.assertIs(manager.audit_manager, audit)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            AuditManagerDep,
            AuthorizationManagerDep,
            ConfigurationManagerDep,
            DeploymentValidatorDep,
            DiagnosticsManagerDep,
            EnterpriseOperationsManagerDep,
            ObservabilityManagerDep,
        )

        for dep in (
            AuthorizationManagerDep,
            AuditManagerDep,
            ConfigurationManagerDep,
            ObservabilityManagerDep,
            DeploymentValidatorDep,
            DiagnosticsManagerDep,
            EnterpriseOperationsManagerDep,
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
    }

    def test_frozen_1610_service_unchanged(self):
        from app.core.dependencies import get_ai_employee_service

        self.assertIsInstance(
            get_ai_employee_service(), AIEmployeeService
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_operations_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.operations as pkg

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
