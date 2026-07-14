"""Operations inspector (Sprint 16.14 — visualise the enterprise operations surface).

Defines :class:`OperationsInspector`, which projects the operations view of the
dashboard — an audit summary, an authorization summary, configuration status,
deployment status, and diagnostics — by *reading* the frozen Sprint 16.11
:class:`EnterpriseOperationsManager`. It never executes a workflow, changes behaviour,
or modifies state.

It uses only the operations manager's *non-mutating* surfaces: it reads the audit trail,
resolves a permission through the authorization policy, and validates configuration,
deployment, and diagnostics — never ``authorize``/``validate_environment`` (which append
an audit record). It observes only: it reads and executes, delegates, and stores
nothing. Strictly additive to Sprints 1.x–16.13, whose modules are left untouched.
"""

from typing import Any, Dict

from app.services.ai_employee.dashboard.models import OperationsDashboard


class OperationsInspector:
    """Projects the operations dashboard from the operations manager (read-only).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``dashboard`` reads the audit trail, authorization
    policy, configuration, deployment, and diagnostics through their non-mutating
    surfaces and reports each as a summary. It is stateless and reads only — it appends
    no audit record and runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def dashboard(self) -> OperationsDashboard:
        """Return the :class:`OperationsDashboard` for the operations surface."""
        return OperationsDashboard(
            audit_summary=self._audit_summary(),
            authorization_summary=self._authorization_summary(),
            configuration_status=self._configuration_status(),
            deployment_status=self._deployment_status(),
            diagnostics=self._diagnostics(),
            dashboard_metadata={"source": "enterprise_operations"},
        )

    # --- sections --------------------------------------------------------
    def _audit_summary(self) -> Dict[str, int]:
        """Return the audit-record count per category (read-only)."""
        counts: Dict[str, int] = {}
        for record in self.operations.audit():
            label = record.category.value
            counts[label] = counts.get(label, 0) + 1
        counts["total"] = sum(counts.values())
        return dict(sorted(counts.items()))

    def _authorization_summary(self) -> Dict[str, Any]:
        """Return an authorization projection from a pure permission read."""
        authorization = self.operations.authorization
        return {
            "system_wildcard": authorization.validate_permission(
                "system", "*"
            )
        }

    def _configuration_status(self) -> Dict[str, Any]:
        """Return the configuration validity projection (read-only)."""
        report = self.operations.validate_configuration()
        return {
            "valid": report.valid,
            "issues": len(report.issues),
            "warnings": len(report.warnings),
        }

    def _deployment_status(self) -> Dict[str, Any]:
        """Return the deployment-readiness projection (non-mutating startup check).

        Loads the effective configuration first (a pure read) so the startup check
        validates the real defaults, then validates deployment readiness directly
        through the :class:`DeploymentValidator` — never ``validate_environment`` (which
        would append an audit record).
        """
        config = self.operations.configuration.load()
        report = self.operations.deployment.validate_startup(config)
        return {"ready": report.ready, "issues": len(report.issues)}

    def _diagnostics(self) -> Dict[str, Any]:
        """Return the diagnostics roll-up projection (read-only)."""
        report = self.operations.diagnostics()
        return {
            "healthy": report.healthy,
            "components": len(report.components),
            "issues": len(report.issues),
        }
