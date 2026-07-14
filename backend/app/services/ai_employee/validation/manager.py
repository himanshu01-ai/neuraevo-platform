"""Production Validation manager (Sprint 16.13 — coordinate production validation).

Defines :class:`ProductionValidationManager`, the coordinator of the Production
Validation Platform. It coordinates the platform's validation surface over its injected
collaborators — the :class:`SystemValidator`, :class:`IntegrationValidator`,
:class:`PerformanceValidator`, :class:`ReliabilityValidator`,
:class:`SecurityValidator`, :class:`CompatibilityValidator`, and
:class:`ValidationReporter` — and *delegates only to the frozen Sprint 16.11*
:class:`EnterpriseOperationsManager` for the platform's overall state:

    validate           (run every validator once -> the raw results)
    full_validation    (the combined final report)
    report             (a scoped validation report)
    readiness          (the production-readiness verdict, with results)
    summary            (the compact production-readiness verdict)

This platform validates only. It never executes a workflow or a capability, never calls
the Workflow Coordinator, and never modifies AI behaviour or an existing service —
platform state is read only through the :class:`EnterpriseOperationsManager`.
Constructor injection only; it holds no mutable state of its own — no static, singleton,
or service-locator state. Strictly additive to Sprints 1.x–16.12, whose modules are
left untouched.
"""

from typing import List

from app.services.ai_employee.validation import common
from app.services.ai_employee.validation.models import (
    IntegrationStatus,
    PerformanceSummary,
    ProductionReadiness,
    ReliabilitySummary,
    SystemStatus,
    ValidationReport,
    ValidationResult,
    ValidationScope,
    ValidationStatus,
)
from app.services.ai_employee.service import HealthState


class ProductionValidationManager:
    """Coordinates production validation over its validators and the operations manager.

    Constructed with an injected :class:`SystemValidator`, :class:`IntegrationValidator`,
    :class:`PerformanceValidator`, :class:`ReliabilityValidator`,
    :class:`SecurityValidator`, :class:`CompatibilityValidator`,
    :class:`ValidationReporter`, and the frozen Sprint 16.11
    :class:`EnterpriseOperationsManager` (constructor injection; it instantiates none).
    It runs the validators, assembles reports, and derives the production-readiness
    verdict, reading the platform's overall state only through the operations manager —
    it validates only and executes no workflow. It holds no mutable state of its own.
    """

    def __init__(
        self,
        system,
        integration,
        performance,
        reliability,
        security,
        compatibility,
        reporter,
        operations,
    ) -> None:
        self.system = system
        self.integration = integration
        self.performance = performance
        self.reliability = reliability
        self.security = security
        self.compatibility = compatibility
        self.reporter = reporter
        self.operations = operations

    # --- validation ------------------------------------------------------
    def validate(self) -> List[ValidationResult]:
        """Run every validator once and return the per-scope :class:`ValidationResult` s."""
        return [
            self.system.validate(),
            self.integration.validate(),
            self.performance.validate(),
            self.reliability.validate(),
            self.security.validate(),
            self.compatibility.validate(),
        ]

    def full_validation(self, sequence: int = 0) -> ValidationReport:
        """Return the combined final :class:`ValidationReport` over every validator."""
        return self.reporter.final_report(self.validate(), sequence)

    def report(
        self, scope: ValidationScope = ValidationScope.FINAL, sequence: int = 0
    ) -> ValidationReport:
        """Return the :class:`ValidationReport` for ``scope`` (runs the needed checks)."""
        if scope == ValidationScope.SYSTEM:
            return self.reporter.system_report(
                self.system.validate(), sequence
            )
        if scope == ValidationScope.INTEGRATION:
            return self.reporter.integration_report(
                self.integration.validate(), sequence
            )
        if scope == ValidationScope.PERFORMANCE:
            return self.reporter.performance_report(
                self.performance.validate(), sequence
            )
        if scope == ValidationScope.SECURITY:
            return self.reporter.security_report(
                self.security.validate(), sequence
            )
        if scope == ValidationScope.RELIABILITY:
            return self.reporter.report(
                ValidationScope.RELIABILITY,
                [self.reliability.validate()],
                sequence,
            )
        if scope == ValidationScope.COMPATIBILITY:
            return self.reporter.report(
                ValidationScope.COMPATIBILITY,
                [self.compatibility.validate()],
                sequence,
            )
        if scope == ValidationScope.READINESS:
            return self.reporter.readiness_report(
                self.readiness(), sequence
            )
        return self.reporter.final_report(self.validate(), sequence)

    # --- readiness -------------------------------------------------------
    def readiness(self) -> ProductionReadiness:
        """Return the detailed production-readiness verdict (with per-scope results)."""
        results = self.validate()
        return self._readiness(results, include_results=True)

    def summary(self) -> ProductionReadiness:
        """Return the compact production-readiness verdict (counts + blockers only)."""
        results = self.validate()
        return self._readiness(results, include_results=False)

    # --- specialised accessors ------------------------------------------
    def system_statuses(self) -> List[SystemStatus]:
        """Return the per-subsystem :class:`SystemStatus` list."""
        return self.system.system_statuses()

    def integration_statuses(self) -> List[IntegrationStatus]:
        """Return the per-integration :class:`IntegrationStatus` list."""
        return self.integration.integration_statuses()

    def performance_summary(self) -> PerformanceSummary:
        """Return the :class:`PerformanceSummary`."""
        return self.performance.summary()

    def reliability_summary(self) -> ReliabilitySummary:
        """Return the :class:`ReliabilitySummary`."""
        return self.reliability.summary()

    # --- helpers ---------------------------------------------------------
    def _readiness(
        self, results: List[ValidationResult], include_results: bool
    ) -> ProductionReadiness:
        """Fold ``results`` and the operations state into a :class:`ProductionReadiness`.

        Readiness requires every validation to be free of blocking (``ERROR``) issues
        *and* the operations manager to report the platform ready. The overall
        :class:`HealthState` is taken from the operations manager — the single platform
        state the manager delegates to. Deterministic; it runs nothing.
        """
        blockers = common.blocking_issues(results)
        passed = sum(
            1 for r in results if r.status == ValidationStatus.PASSED
        )
        enterprise = self.operations.system_status()
        ready = not blockers and enterprise.ready
        return ProductionReadiness(
            ready=ready,
            state=enterprise.state if enterprise.state else HealthState.UNHEALTHY,
            passed_validations=passed,
            total_validations=len(results),
            blocking_issues=blockers,
            results=list(results) if include_results else [],
            detail=(
                "production ready"
                if ready
                else "production not ready"
            ),
            readiness_metadata={
                "operations_ready": enterprise.ready,
                "blocking_issue_count": len(blockers),
            },
        )
