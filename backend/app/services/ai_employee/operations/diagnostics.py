"""Diagnostics manager (Sprint 16.11 — aggregate platform diagnostics).

Defines :class:`DiagnosticsManager`, which aggregates the platform's operational
signals into immutable :class:`DiagnosticsReport`\\ s. ``diagnostics`` reports the
per-subsystem component health and any problems; ``health_summary`` is a compact
health roll-up; ``dependency_report`` surfaces the deployment dependency checks; and
``system_report`` combines components, dependencies, and aggregate metrics into one
report.

It aggregates by *reading* its injected collaborators — the Sprint 16.11
:class:`ObservabilityManager` and :class:`DeploymentValidator` — and connects to no
external monitoring system. It is deterministic and stateless: it reports only and
executes, delegates, and stores nothing. Strictly additive to Sprints 1.x–16.10,
whose modules are left untouched.
"""

from app.services.ai_employee.operations.deployment import DeploymentValidator
from app.services.ai_employee.operations.models import DiagnosticsReport
from app.services.ai_employee.operations.observability import (
    ObservabilityManager,
)


class DiagnosticsManager:
    """Aggregates platform diagnostics from observability and deployment (read-only).

    Constructed with an injected :class:`ObservabilityManager` and
    :class:`DeploymentValidator` (constructor injection; it instantiates none).
    ``diagnostics`` and ``health_summary`` roll up component health;
    ``dependency_report`` surfaces the deployment dependency checks; and
    ``system_report`` combines components, dependencies, and metrics. Stateless; it
    reads only and connects to no external monitoring.
    """

    def __init__(
        self,
        observability_manager: ObservabilityManager,
        deployment_validator: DeploymentValidator,
    ) -> None:
        self.observability = observability_manager
        self.deployment = deployment_validator

    def diagnostics(self) -> DiagnosticsReport:
        """Report per-subsystem component health and any unhealthy components."""
        components = self.observability.component_status()
        issues = [
            f"{c.name} is {c.state.value}"
            for c in components
            if not c.healthy
        ]
        healthy = not issues
        return DiagnosticsReport(
            healthy=healthy,
            summary=self._summary(components, healthy),
            components=components,
            issues=issues,
        )

    def health_summary(self) -> DiagnosticsReport:
        """Return a compact component-health roll-up."""
        components = self.observability.component_status()
        healthy = all(c.healthy for c in components)
        return DiagnosticsReport(
            healthy=healthy,
            summary=self._summary(components, healthy),
            components=components,
        )

    def dependency_report(self) -> DiagnosticsReport:
        """Surface the deployment dependency checks as a diagnostics report."""
        report = self.deployment.validate_dependencies()
        return DiagnosticsReport(
            healthy=report.ready,
            summary=("dependencies ready" if report.ready else "dependencies not ready"),
            dependencies=dict(report.checks),
            issues=list(report.issues),
        )

    def system_report(self) -> DiagnosticsReport:
        """Combine components, dependencies, and aggregate metrics into one report."""
        components = self.observability.component_status()
        dependencies = self.deployment.validate_dependencies()
        metrics = self.observability.metrics()
        issues = [
            f"{c.name} is {c.state.value}"
            for c in components
            if not c.healthy
        ] + list(dependencies.issues)
        healthy = not issues
        return DiagnosticsReport(
            healthy=healthy,
            summary=("system healthy" if healthy else "system has issues"),
            components=components,
            dependencies=dict(dependencies.checks),
            metrics=metrics,
            issues=issues,
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _summary(components, healthy) -> str:
        """Return a deterministic ``N/total healthy`` summary line."""
        up = sum(1 for component in components if component.healthy)
        return f"{up}/{len(components)} components healthy"
