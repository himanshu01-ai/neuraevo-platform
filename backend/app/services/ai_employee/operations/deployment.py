"""Deployment validator (Sprint 16.11 — validate deployment readiness).

Defines :class:`DeploymentValidator`, which validates that the platform is ready to
run, deterministically and offline. ``validate_dependencies`` checks that every
required subsystem dependency is healthy; ``validate_components`` checks that every
reported subsystem is healthy; ``validate_configuration`` runs the configuration
through the :class:`ConfigurationManager`; and ``validate_startup`` aggregates all
three into one readiness verdict. Each returns an immutable :class:`DeploymentReport`.

It validates by *reading* the injected :class:`ConfigurationManager` and the frozen
Sprint 16.10 :class:`HealthManager` — it deploys nothing, starts nothing, and talks
to no cloud SDK, container runtime, or orchestrator. Deterministic and stateless.
Strictly additive to Sprints 1.x–16.10, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.operations.configuration import (
    ConfigurationManager,
)
from app.services.ai_employee.operations.models import (
    CheckStatus,
    DeploymentReport,
)
from app.services.ai_employee.service import HealthManager, HealthState
from app.services.ai_employee.service.health import HEALTH_COMPONENTS

_HEALTHY = HealthState.HEALTHY.value


class DeploymentValidator:
    """Validates deployment readiness from configuration and health (deterministic).

    Constructed with an injected :class:`ConfigurationManager` and
    :class:`HealthManager`, plus the ``required_dependencies`` the deployment needs
    (defaults to the canonical platform subsystems). Each ``validate_*`` returns a
    :class:`DeploymentReport`; ``validate_startup`` aggregates dependencies,
    components, and configuration into one readiness verdict. Stateless; it reads only
    and deploys/starts nothing.
    """

    def __init__(
        self,
        configuration_manager: ConfigurationManager,
        health_manager: HealthManager,
        required_dependencies: Optional[List[str]] = None,
    ) -> None:
        self.configuration_manager = configuration_manager
        self.health_manager = health_manager
        self._required_dependencies = list(
            required_dependencies or HEALTH_COMPONENTS
        )

    def validate_dependencies(self) -> DeploymentReport:
        """Validate that every required subsystem dependency is healthy."""
        components = self.health_manager.health().components
        checks: Dict[str, str] = {}
        issues: List[str] = []
        for dependency in self._required_dependencies:
            ok = components.get(dependency) == _HEALTHY
            checks[dependency] = (
                CheckStatus.PASS.value if ok else CheckStatus.FAIL.value
            )
            if not ok:
                issues.append(f"dependency not ready: {dependency}")
        return DeploymentReport(
            ready=not issues,
            checks=checks,
            issues=issues,
            detail="dependencies",
        )

    def validate_components(self) -> DeploymentReport:
        """Validate that every reported subsystem component is healthy."""
        components = self.health_manager.health().components
        checks: Dict[str, str] = {}
        issues: List[str] = []
        for name, state_value in components.items():
            ok = state_value == _HEALTHY
            checks[name] = (
                CheckStatus.PASS.value if ok else CheckStatus.FAIL.value
            )
            if not ok:
                issues.append(f"component unhealthy: {name}")
        return DeploymentReport(
            ready=not issues,
            checks=checks,
            issues=issues,
            detail="components",
        )

    def validate_configuration(
        self, config: Optional[Dict[str, Any]] = None
    ) -> DeploymentReport:
        """Validate the configuration through the :class:`ConfigurationManager`."""
        report = self.configuration_manager.validate(config or {})
        return DeploymentReport(
            ready=report.valid,
            checks={
                "configuration": (
                    CheckStatus.PASS.value
                    if report.valid
                    else CheckStatus.FAIL.value
                )
            },
            issues=list(report.issues),
            detail="configuration",
        )

    def validate_startup(
        self, config: Optional[Dict[str, Any]] = None
    ) -> DeploymentReport:
        """Aggregate dependency, component, and configuration checks into one verdict."""
        dependencies = self.validate_dependencies()
        components = self.validate_components()
        configuration = self.validate_configuration(config)
        checks: Dict[str, str] = {}
        for name, status in dependencies.checks.items():
            checks[f"dependency:{name}"] = status
        for name, status in components.checks.items():
            checks[f"component:{name}"] = status
        checks["configuration"] = configuration.checks["configuration"]
        issues = [
            *dependencies.issues,
            *components.issues,
            *configuration.issues,
        ]
        return DeploymentReport(
            ready=(
                dependencies.ready
                and components.ready
                and configuration.ready
            ),
            checks=checks,
            issues=issues,
            detail="startup",
        )
