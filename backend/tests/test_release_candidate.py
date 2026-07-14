"""Unit + integration tests for the Sprint 16.15 Release Candidate backend.

Exercises the release subsystem: the :class:`ContractManager`, the
:class:`DependencyAuditor`, the :class:`ConfigurationAuditor`, the
:class:`DocumentationGenerator`, the :class:`BackupValidator`, the
:class:`ReleaseReporter`, and the :class:`ReleaseManager` that coordinates them over the
frozen Sprint 16.14 :class:`DeveloperDashboardManager`.

The Release Candidate backend adds release infrastructure only — it adds no business
feature, redesigns no subsystem, never executes a workflow, and never modifies platform
state. It reads state through the frozen dashboard, production, operations, and
experience managers (which here run over deterministic recording doubles), and it
connects to no deployment, Docker/Kubernetes, CI/CD, cloud, or package manager.

Covers, as the sprint requires: contract validation, dependency audit, configuration
audit, documentation generation, backup validation, release reports, release readiness,
DTO immutability, DI wiring, and regression (Sprints 16.1–16.14 unchanged; the release
sub-package imports nothing forbidden). Also asserts the read-only invariant: the audit
trail is unchanged by release preparation.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_release_candidate
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import AIEmployee, EmployeeProfile
from app.services.ai_employee.dashboard import (
    AgentInspector,
    CapabilityInspector,
    DashboardReporter,
    DeveloperDashboardManager,
    ExperienceInspector,
    MemoryInspector,
    OperationsInspector,
    RecoveryInspector,
    SchedulerInspector,
    ValidationInspector,
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
from app.services.ai_employee.release import (
    RELEASE_VERSION,
    BackupReport,
    BackupValidator,
    ConfigurationAudit,
    ConfigurationAuditor,
    ContractManager,
    DependencyAuditor,
    DependencyReport,
    DocumentationGenerator,
    DocumentationReport,
    ReleaseCandidateSummary,
    ReleaseDecision,
    ReleaseIssue,
    ReleaseManager,
    ReleaseReport,
    ReleaseReporter,
    ReleaseSeverity,
    ReleaseStatus,
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
            workflow_status=_COMPLETED,
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


def _dashboard(operations, production, experience) -> DeveloperDashboardManager:
    service = operations.service
    return DeveloperDashboardManager(
        WorkflowInspector(service),
        AgentInspector(service),
        MemoryInspector(operations),
        SchedulerInspector(operations),
        RecoveryInspector(operations),
        CapabilityInspector(experience),
        ValidationInspector(production),
        ExperienceInspector(experience),
        OperationsInspector(operations),
        DashboardReporter(),
        production,
    )


class _Release:
    """A fully-wired release manager over shared recording doubles (test convenience)."""

    def __init__(self, components=None) -> None:
        self.operations = _operations(components)
        self.service = self.operations.service
        self.production = _production(self.operations)
        self.experience = _experience(self.service)
        self.dashboard = _dashboard(
            self.operations, self.production, self.experience
        )
        self.contract = ContractManager(self.production)
        self.dependency = DependencyAuditor(self.production)
        self.configuration = ConfigurationAuditor(self.operations)
        self.documentation = DocumentationGenerator(self.dashboard)
        self.backup = BackupValidator(self.dashboard)
        self.manager = ReleaseManager(
            self.contract,
            self.dependency,
            self.configuration,
            self.documentation,
            self.backup,
            ReleaseReporter(),
            self.dashboard,
        )


def _degraded(*names) -> dict:
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
# Contract validation
# =====================================================================
class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = _Release().contract

    def test_validate_api(self):
        status = self.contract.validate_api()
        self.assertIsInstance(status, ReleaseStatus)
        self.assertTrue(status.passed)
        self.assertGreater(status.status_metadata["methods_checked"], 0)

    def test_validate_dtos(self):
        status = self.contract.validate_dtos()
        self.assertTrue(status.passed)  # every platform DTO is frozen

    def test_validate_dependencies(self):
        status = self.contract.validate_dependencies()
        self.assertTrue(status.passed)

    def test_freeze_summary(self):
        status = self.contract.freeze_summary()
        self.assertEqual(status.name, "contracts")
        self.assertTrue(status.passed)
        self.assertTrue(status.status_metadata["api_passed"])


# =====================================================================
# Dependency audit
# =====================================================================
class DependencyAuditTests(unittest.TestCase):
    def setUp(self):
        self.auditor = _Release().dependency

    def test_versions(self):
        versions = self.auditor.dependency_versions()
        self.assertIn("python", versions)
        self.assertIn("pydantic", versions)

    def test_validate(self):
        report = self.auditor.validate()
        self.assertIsInstance(report, DependencyReport)
        self.assertTrue(report.ok)
        self.assertTrue(report.module_integrity)
        self.assertTrue(report.versions["pydantic"].startswith("2"))

    def test_no_architecture_violations(self):
        report = self.auditor.validate()
        arch_issues = [
            issue for issue in report.issues if "architecture" in issue.message
        ]
        self.assertEqual(arch_issues, [])


# =====================================================================
# Configuration audit
# =====================================================================
class ConfigurationAuditTests(unittest.TestCase):
    def setUp(self):
        self.auditor = _Release().configuration

    def test_validate(self):
        audit = self.auditor.validate()
        self.assertIsInstance(audit, ConfigurationAudit)
        self.assertTrue(audit.ok)
        self.assertTrue(audit.complete)
        self.assertTrue(audit.required_present)
        self.assertTrue(audit.environment_compatible)
        self.assertIn("environment", audit.defaults)

    def test_missing_environment_blocks(self):
        operations = _operations()
        # A configuration manager whose defaults omit the environment key.
        operations.configuration = ConfigurationManager(
            defaults={"service_name": "ai-employee"},
            required_keys=["service_name"],
        )
        audit = ConfigurationAuditor(operations).validate()
        self.assertFalse(audit.environment_compatible)
        self.assertFalse(audit.ok)


# =====================================================================
# Documentation generation
# =====================================================================
class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.generator = _Release().documentation

    def test_generate(self):
        report = self.generator.generate()
        self.assertIsInstance(report, DocumentationReport)
        self.assertTrue(report.architecture_summary)
        self.assertIn("service", report.module_inventory)
        self.assertIn("AIEmployeeService", report.service_inventory)
        self.assertIn("browser", report.capability_inventory)
        self.assertTrue(report.release_notes)

    def test_release_notes_mention_version(self):
        notes = self.generator.release_notes()
        self.assertTrue(any(RELEASE_VERSION in note for note in notes))


# =====================================================================
# Backup validation
# =====================================================================
class BackupTests(unittest.TestCase):
    def setUp(self):
        self.validator = _Release().backup

    def test_validate(self):
        report = self.validator.validate()
        self.assertIsInstance(report, BackupReport)
        self.assertTrue(report.ok)
        self.assertTrue(report.backup_integrity)
        self.assertTrue(report.restore_integrity)
        self.assertTrue(report.snapshot_consistency)

    def test_snapshot_is_reproducible(self):
        first = self.validator.validate()
        second = self.validator.validate()
        self.assertEqual(first, second)


# =====================================================================
# Release reports + readiness + manager coordination
# =====================================================================
class ReleaseManagerTests(unittest.TestCase):
    def test_freeze_contracts(self):
        status = _Release().manager.freeze_contracts()
        self.assertEqual(status.name, "contracts")
        self.assertTrue(status.passed)

    def test_audit(self):
        status = _Release().manager.audit()
        self.assertEqual(status.name, "release_audit")
        self.assertTrue(status.passed)
        self.assertTrue(status.status_metadata["dependencies_ok"])

    def test_release_readiness(self):
        status = _Release().manager.release_readiness()
        self.assertIsInstance(status, ReleaseStatus)
        self.assertTrue(status.passed)

    def test_generate_release_go(self):
        report = _Release().manager.generate_release()
        self.assertIsInstance(report, ReleaseReport)
        self.assertEqual(report.decision, ReleaseDecision.GO)
        self.assertTrue(report.ready)
        self.assertTrue(report.production_ready)
        self.assertEqual(report.version, RELEASE_VERSION)
        self.assertEqual(report.issues, [])

    def test_summary_go(self):
        summary = _Release().manager.summary()
        self.assertIsInstance(summary, ReleaseCandidateSummary)
        self.assertEqual(summary.decision, ReleaseDecision.GO)
        self.assertTrue(summary.ready)
        self.assertTrue(summary.contracts_frozen)
        self.assertTrue(summary.dependencies_ok)
        self.assertTrue(summary.configuration_ok)
        self.assertTrue(summary.backup_ok)
        self.assertEqual(summary.blocking_issues, 0)

    def test_degraded_platform_is_no_go(self):
        manager = _Release(_degraded("recovery")).manager
        report = manager.generate_release()
        self.assertEqual(report.decision, ReleaseDecision.NO_GO)
        self.assertFalse(report.ready)
        self.assertFalse(report.production_ready)
        self.assertTrue(report.issues)
        self.assertFalse(manager.summary().ready)

    def test_manager_holds_only_declared_collaborators(self):
        manager = _Release().manager
        self.assertEqual(
            set(vars(manager)),
            {
                "contract",
                "dependency",
                "configuration",
                "documentation",
                "backup",
                "reporter",
                "dashboard",
            },
        )

    def test_release_preparation_is_read_only(self):
        release = _Release()
        release.operations.submit_task(_request())
        before = len(release.operations.audit())
        release.manager.generate_release()
        release.manager.summary()
        release.manager.release_readiness()
        self.assertEqual(len(release.operations.audit()), before)


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def test_status_and_issue_frozen(self):
        with self.assertRaises(ValidationError):
            ReleaseStatus(name="n").passed = True
        with self.assertRaises(ValidationError):
            ReleaseIssue(
                issue_id="i1",
                severity=ReleaseSeverity.BLOCKER,
                message="m",
            ).message = "x"

    def test_reports_frozen(self):
        with self.assertRaises(ValidationError):
            DependencyReport().ok = True
        with self.assertRaises(ValidationError):
            ConfigurationAudit().complete = True
        with self.assertRaises(ValidationError):
            DocumentationReport().architecture_summary = "x"
        with self.assertRaises(ValidationError):
            BackupReport().ok = True

    def test_release_report_and_summary_frozen(self):
        report = _Release().manager.generate_release()
        with self.assertRaises(ValidationError):
            report.decision = ReleaseDecision.NO_GO
        with self.assertRaises(ValidationError):
            ReleaseCandidateSummary().ready = True

    def test_issue_requires_non_empty_message(self):
        with self.assertRaises(ValidationError):
            ReleaseIssue(
                issue_id="i1", severity=ReleaseSeverity.INFO, message=""
            )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_backup_validator,
            get_configuration_auditor,
            get_contract_manager,
            get_dependency_auditor,
            get_documentation_generator,
            get_release_reporter,
        )

        self.assertIsInstance(get_contract_manager(), ContractManager)
        self.assertIsInstance(get_dependency_auditor(), DependencyAuditor)
        self.assertIsInstance(
            get_configuration_auditor(), ConfigurationAuditor
        )
        self.assertIsInstance(
            get_documentation_generator(), DocumentationGenerator
        )
        self.assertIsInstance(get_backup_validator(), BackupValidator)
        self.assertIsInstance(get_release_reporter(), ReleaseReporter)

    def test_manager_provider_wires_collaborators(self):
        from app.core.dependencies import get_release_manager

        manager = get_release_manager()
        self.assertIsInstance(manager, ReleaseManager)
        self.assertIsInstance(manager.contract, ContractManager)
        self.assertIsInstance(manager.dependency, DependencyAuditor)
        self.assertIsInstance(manager.configuration, ConfigurationAuditor)
        self.assertIsInstance(
            manager.documentation, DocumentationGenerator
        )
        self.assertIsInstance(manager.backup, BackupValidator)
        self.assertIsInstance(manager.reporter, ReleaseReporter)
        self.assertIsInstance(
            manager.dashboard, DeveloperDashboardManager
        )

    def test_manager_provider_shares_state(self):
        from app.core.dependencies import get_release_manager

        manager = get_release_manager()
        # Every component reads one shared platform state via the dashboard.
        self.assertIs(
            manager.dashboard.production, manager.contract.production
        )
        self.assertIs(
            manager.dashboard.production, manager.dependency.production
        )
        self.assertIs(
            manager.dashboard.production.operations,
            manager.configuration.operations,
        )
        self.assertIs(manager.dashboard, manager.backup.dashboard)

    def test_manager_provider_uses_injected(self):
        from app.core.dependencies import get_release_manager

        reporter = ReleaseReporter()
        manager = get_release_manager(reporter=reporter)
        self.assertIs(manager.reporter, reporter)

    def test_manager_provider_is_go(self):
        from app.core.dependencies import get_release_manager

        # The fully-wired backend is a viable release candidate.
        self.assertEqual(
            get_release_manager().summary().decision, ReleaseDecision.GO
        )

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            BackupValidatorDep,
            ConfigurationAuditorDep,
            ContractManagerDep,
            DependencyAuditorDep,
            DocumentationGeneratorDep,
            ReleaseManagerDep,
            ReleaseReporterDep,
        )

        for dep in (
            ContractManagerDep,
            DependencyAuditorDep,
            ConfigurationAuditorDep,
            DocumentationGeneratorDep,
            BackupValidatorDep,
            ReleaseReporterDep,
            ReleaseManagerDep,
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
        "docker",
        "kubernetes",
    }

    def test_frozen_1614_dashboard_unchanged(self):
        from app.core.dependencies import get_developer_dashboard_manager

        self.assertIsInstance(
            get_developer_dashboard_manager(), DeveloperDashboardManager
        )

    def test_frozen_1613_production_unchanged(self):
        from app.core.dependencies import get_production_validation_manager

        self.assertIsInstance(
            get_production_validation_manager(),
            ProductionValidationManager,
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_release_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.release as pkg

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
