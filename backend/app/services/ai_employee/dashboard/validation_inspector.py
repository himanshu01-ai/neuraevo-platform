"""Validation inspector (Sprint 16.14 — visualise production validation).

Defines :class:`ValidationInspector`, which projects the validation view of the
dashboard — production readiness, validation reports, and validation issues — by
*reading* the frozen Sprint 16.13 :class:`ProductionValidationManager`. It never
executes a workflow, changes behaviour, or modifies state.

The manager's readiness verdict and final report supply the readiness flags, per-scope
results, and blocking issues. It observes only: it reads and executes, delegates, and
stores nothing. Strictly additive to Sprints 1.x–16.13, whose modules are left
untouched.
"""

from typing import Any, Dict, List

from app.services.ai_employee.dashboard.models import ValidationDashboard


class ValidationInspector:
    """Projects the validation dashboard from the production validator (read-only).

    Constructed with an injected :class:`ProductionValidationManager` (constructor
    injection; it instantiates none). ``dashboard`` reads the readiness verdict and the
    final validation report and reports the readiness flags, per-scope results, and
    blocking issues. It is stateless and reads only — it runs nothing.
    """

    def __init__(self, production) -> None:
        self.production = production

    def dashboard(self) -> ValidationDashboard:
        """Return the :class:`ValidationDashboard` for the platform validation."""
        readiness = self.production.readiness()
        report = self.production.full_validation()
        results: List[Dict[str, Any]] = [
            {
                "scope": result.scope.value,
                "status": result.status.value,
                "passed": result.passed,
                "issue_count": len(result.issues),
            }
            for result in report.results
        ]
        issues: List[Dict[str, Any]] = [
            {
                "issue_id": issue.issue_id,
                "severity": issue.severity.value,
                "message": issue.message,
                "component": issue.component,
            }
            for issue in readiness.blocking_issues
        ]
        return ValidationDashboard(
            ready=readiness.ready,
            state=readiness.state.value,
            passed_validations=readiness.passed_validations,
            total_validations=readiness.total_validations,
            results=results,
            issues=issues,
            dashboard_metadata={"source": "production_validation"},
        )
