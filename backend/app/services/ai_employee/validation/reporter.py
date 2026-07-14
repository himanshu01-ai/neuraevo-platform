"""Validation reporter (Sprint 16.13 — format deterministic validation reports).

Defines :class:`ValidationReporter`, which formats already-computed
:class:`ValidationResult` s (and the :class:`ProductionReadiness` verdict) into
immutable :class:`ValidationReport` s — a system, integration, performance, security,
readiness, or final report.

It is a pure formatter: it composes the results it is given into report DTOs and
aggregates their pass/fail and issues, executing nothing beyond deterministic assembly.
There is no external dashboard, scanner, or benchmark — it observes only. Strictly
additive to Sprints 1.x–16.12, whose modules are left untouched.
"""

from typing import List

from app.services.ai_employee.validation.models import (
    ProductionReadiness,
    ValidationReport,
    ValidationResult,
    ValidationScope,
)


class ValidationReporter:
    """Formats validation results into immutable reports (pure assembly, no execution).

    Stateless. ``system_report`` / ``integration_report`` / ``performance_report`` /
    ``security_report`` wrap a single scoped result; ``readiness_report`` renders the
    :class:`ProductionReadiness` verdict; and ``final_report`` bundles every result into
    the combined report. It reads the results it is given only — it runs nothing.
    """

    def report(
        self,
        scope: ValidationScope,
        results: List[ValidationResult],
        sequence: int = 0,
    ) -> ValidationReport:
        """Assemble a :class:`ValidationReport` bundling ``results`` for ``scope``."""
        results = list(results)
        issues = [issue for result in results for issue in result.issues]
        passed = all(result.passed for result in results)
        passed_count = sum(1 for result in results if result.passed)
        return ValidationReport(
            report_id=f"validation-{scope.value.lower()}",
            scope=scope,
            passed=passed,
            results=results,
            issues=issues,
            summary=(
                f"{passed_count}/{len(results)} validation(s) passed; "
                f"{len(issues)} issue(s)"
            ),
            generated_sequence=sequence,
            report_metadata={"result_count": len(results)},
        )

    # --- scoped wrappers -------------------------------------------------
    def system_report(
        self, result: ValidationResult, sequence: int = 0
    ) -> ValidationReport:
        """Assemble the system :class:`ValidationReport`."""
        return self.report(ValidationScope.SYSTEM, [result], sequence)

    def integration_report(
        self, result: ValidationResult, sequence: int = 0
    ) -> ValidationReport:
        """Assemble the integration :class:`ValidationReport`."""
        return self.report(ValidationScope.INTEGRATION, [result], sequence)

    def performance_report(
        self, result: ValidationResult, sequence: int = 0
    ) -> ValidationReport:
        """Assemble the performance :class:`ValidationReport`."""
        return self.report(ValidationScope.PERFORMANCE, [result], sequence)

    def security_report(
        self, result: ValidationResult, sequence: int = 0
    ) -> ValidationReport:
        """Assemble the security :class:`ValidationReport`."""
        return self.report(ValidationScope.SECURITY, [result], sequence)

    def final_report(
        self, results: List[ValidationResult], sequence: int = 0
    ) -> ValidationReport:
        """Assemble the combined final :class:`ValidationReport` over every result."""
        return self.report(ValidationScope.FINAL, results, sequence)

    # --- readiness -------------------------------------------------------
    def readiness_report(
        self, readiness: ProductionReadiness, sequence: int = 0
    ) -> ValidationReport:
        """Render the :class:`ProductionReadiness` verdict as a readiness report."""
        return ValidationReport(
            report_id="validation-readiness",
            scope=ValidationScope.READINESS,
            passed=readiness.ready,
            results=list(readiness.results),
            issues=list(readiness.blocking_issues),
            summary=(
                f"production {'ready' if readiness.ready else 'not ready'}; "
                f"{readiness.passed_validations}/"
                f"{readiness.total_validations} validation(s) passed"
            ),
            generated_sequence=sequence,
            report_metadata={"state": readiness.state.value},
        )
