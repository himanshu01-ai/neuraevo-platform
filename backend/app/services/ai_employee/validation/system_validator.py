"""System validator (Sprint 16.13 — validate platform subsystems by reading state).

Defines :class:`SystemValidator`, which validates that each platform subsystem —
Planning, Runtime, Capabilities, AI Employee, Memory, Scheduler, Recovery, and
Operations — is present and healthy, by *reading* the frozen Sprint 16.11
:class:`EnterpriseOperationsManager`'s status surface. It never executes a workflow,
starts a subsystem, or changes behaviour.

Health for the observable subsystems comes from the operations manager's
enterprise/component status (which projects the frozen Sprint 16.10
:class:`HealthManager`); the Capabilities seam is validated through its Runtime host and
Operations through the enterprise readiness. It observes only: it validates and
executes, delegates, and stores nothing. Strictly additive to Sprints 1.x–16.12, whose
modules are left untouched.
"""

from typing import Dict, List

from app.services.ai_employee.validation import common
from app.services.ai_employee.validation.models import (
    SystemStatus,
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
)
from app.services.ai_employee.service import HealthState

# The canonical subsystems the platform must expose, in report order.
_SUBSYSTEMS = (
    "planning",
    "runtime",
    "capabilities",
    "ai_employee",
    "memory",
    "scheduler",
    "recovery",
    "operations",
)

# Subsystems whose failure blocks production readiness (ERROR); others warn.
_CRITICAL = {"planning", "runtime", "ai_employee", "operations"}


class SystemValidator:
    """Validates each platform subsystem is present and healthy (read-only).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``system_statuses`` projects each subsystem into a
    :class:`SystemStatus`; ``validate`` folds them into a single
    :class:`ValidationResult`. It reads the operations status surface only — it runs and
    starts nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def system_statuses(self) -> List[SystemStatus]:
        """Return a :class:`SystemStatus` for each canonical subsystem."""
        enterprise = self.operations.system_status()
        components: Dict[str, bool] = {
            component.name: component.healthy
            for component in enterprise.components
        }
        runtime_healthy = components.get("runtime", False)
        statuses: List[SystemStatus] = []
        for name in _SUBSYSTEMS:
            if name in components:
                healthy = components[name]
            elif name == "capabilities":
                # Capabilities execute within the Runtime host; validate that seam.
                healthy = runtime_healthy
            elif name == "operations":
                healthy = enterprise.ready
            else:
                healthy = False
            statuses.append(
                SystemStatus(
                    name=name,
                    present=True,
                    healthy=healthy,
                    state=(
                        HealthState.HEALTHY
                        if healthy
                        else HealthState.UNHEALTHY
                    ),
                    detail="healthy" if healthy else "unhealthy",
                )
            )
        return statuses

    def validate(self) -> ValidationResult:
        """Return the aggregate system :class:`ValidationResult`."""
        statuses = self.system_statuses()
        issues = []
        for status in statuses:
            if status.healthy:
                continue
            severity = (
                ValidationSeverity.ERROR
                if status.name in _CRITICAL
                else ValidationSeverity.WARNING
            )
            issues.append(
                common.issue(
                    issue_id=f"system-{status.name}",
                    message=f"subsystem not healthy: {status.name}",
                    severity=severity,
                    component=status.name,
                    detail=status.detail,
                )
            )
        healthy = sum(1 for s in statuses if s.healthy)
        return common.result(
            name="system subsystems",
            scope=ValidationScope.SYSTEM,
            issues=issues,
            detail=f"{healthy}/{len(statuses)} subsystems healthy",
            metadata={"subsystem_count": len(statuses)},
        )
