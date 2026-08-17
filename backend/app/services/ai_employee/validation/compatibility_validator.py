"""Compatibility validator (Sprint 16.13 — validate DI graph and module compatibility).

Defines :class:`CompatibilityValidator`, which validates that the platform is
internally compatible by *reading* the wired DI graph and the frozen Sprint 16.11
:class:`EnterpriseOperationsManager`. It checks the DI graph (every operations
collaborator is wired and the service instance is shared), configuration compatibility
(the default configuration validates), provider compatibility (every canonical
subsystem is represented in the health report), and module compatibility (each platform
package imports and exposes its coordinator).

Each check is a deterministic read/import — it constructs no new graph, starts nothing,
and changes no behaviour. It observes only: it validates and executes, delegates, and
stores nothing. Strictly additive to Sprints 1.x–16.12, whose modules are left
untouched.
"""

from typing import List

from app.services.ai_employee.service.health import HEALTH_COMPONENTS
from app.services.ai_employee.validation import common
from app.services.ai_employee.validation.models import (
    ValidationIssue,
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
)

# The operations collaborators the DI graph must wire (attribute -> present).
_OPERATIONS_COLLABORATORS = (
    "authorization",
    "audit_manager",
    "observability",
    "configuration",
    "deployment",
    "diagnostics_manager",
    "service",
)

# Each platform package and the coordinator export that proves it is module-compatible.
_MODULE_COORDINATORS = (
    ("app.services.ai_employee.service", "AIEmployeeService"),
    ("app.services.ai_employee.operations", "EnterpriseOperationsManager"),
    ("app.services.ai_employee.experience", "ExperienceIntelligenceManager"),
)


class CompatibilityValidator:
    """Validates DI graph and module compatibility (read-only, no execution).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``validate`` runs the DI-graph, configuration,
    provider, and module-compatibility checks and folds them into a
    :class:`ValidationResult`. It reads the wired graph and imports package modules only
    — it constructs no graph and runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def validate(self) -> ValidationResult:
        """Return the aggregate compatibility :class:`ValidationResult`."""
        issues: List[ValidationIssue] = []
        issues.extend(self._di_graph_issues())
        issues.extend(self._configuration_issues())
        issues.extend(self._provider_issues())
        issues.extend(self._module_issues())
        return common.result(
            name="platform compatibility",
            scope=ValidationScope.COMPATIBILITY,
            issues=issues,
            detail=(
                "platform is internally compatible"
                if not issues
                else f"{len(issues)} compatibility concern(s)"
            ),
            metadata={"checks": ["di_graph", "configuration",
                                 "providers", "modules"]},
        )

    # --- checks ----------------------------------------------------------
    def _di_graph_issues(self) -> List[ValidationIssue]:
        """Validate every operations collaborator is wired and the service is shared."""
        issues: List[ValidationIssue] = []
        for name in _OPERATIONS_COLLABORATORS:
            if getattr(self.operations, name, None) is None:
                issues.append(
                    common.issue(
                        issue_id=f"compatibility-di-{name}",
                        message=f"operations collaborator not wired: {name}",
                        severity=ValidationSeverity.ERROR,
                        component="di-graph",
                    )
                )
        shared = getattr(self.operations.observability, "service", None)
        if shared is not None and shared is not self.operations.service:
            issues.append(
                common.issue(
                    issue_id="compatibility-di-shared-service",
                    message="observability does not share the service instance",
                    severity=ValidationSeverity.ERROR,
                    component="di-graph",
                )
            )
        return issues

    def _configuration_issues(self) -> List[ValidationIssue]:
        """Validate the default operational configuration is valid."""
        report = self.operations.validate_configuration()
        return [
            common.issue(
                issue_id=f"compatibility-config-{index}",
                message=f"configuration issue: {problem}",
                severity=ValidationSeverity.ERROR,
                component="configuration",
            )
            for index, problem in enumerate(report.issues)
        ]

    def _provider_issues(self) -> List[ValidationIssue]:
        """Validate every canonical subsystem is represented in the health report."""
        reported = {
            component.name
            for component in self.operations.observability.component_status()
        }
        return [
            common.issue(
                issue_id=f"compatibility-provider-{name}",
                message=f"subsystem not represented: {name}",
                severity=ValidationSeverity.WARNING,
                component="providers",
            )
            for name in HEALTH_COMPONENTS
            if name not in reported
        ]

    def _module_issues(self) -> List[ValidationIssue]:
        """Validate each platform package imports and exposes its coordinator."""
        import importlib

        issues: List[ValidationIssue] = []
        for module_name, coordinator in _MODULE_COORDINATORS:
            try:
                module = importlib.import_module(module_name)
                ok = hasattr(module, coordinator)
            except Exception as exc:  # noqa: BLE001 - reported, never raised
                ok = False
                issues.append(
                    common.issue(
                        issue_id=f"compatibility-module-{module_name}",
                        message=f"module not importable: {module_name}",
                        severity=ValidationSeverity.ERROR,
                        component="modules",
                        detail=exc.__class__.__name__,
                    )
                )
                continue
            if not ok:
                issues.append(
                    common.issue(
                        issue_id=f"compatibility-module-{module_name}",
                        message=(
                            f"module missing coordinator: "
                            f"{module_name}.{coordinator}"
                        ),
                        severity=ValidationSeverity.ERROR,
                        component="modules",
                    )
                )
        return issues
