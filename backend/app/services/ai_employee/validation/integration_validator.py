"""Integration validator (Sprint 16.13 — validate subsystem integration wiring).

Defines :class:`IntegrationValidator`, which validates the integration points between
platform subsystems — Planning ↔ Runtime, Runtime ↔ Capabilities, AIEmployee ↔
Service, Service ↔ Operations, Memory ↔ Persistence, Scheduler ↔ Recovery, and
Approval ↔ Notification — by *reading* the wired DI graph and the health surface of the
frozen Sprint 16.11 :class:`EnterpriseOperationsManager`. It never exercises an
interaction, executes a workflow, or changes behaviour.

Each integration is validated structurally (are both sides wired, and is a shared
instance shared where expected) and by health (are both sides up) — no call crosses a
seam. It observes only: it validates and executes, delegates, and stores nothing.
Strictly additive to Sprints 1.x–16.12, whose modules are left untouched.
"""

from typing import Dict, List, Optional, Tuple

from app.services.ai_employee.validation import common
from app.services.ai_employee.validation.models import (
    IntegrationStatus,
    ValidationIssue,
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
)

# One (status, optional-issue) pair per validated integration point.
_Check = Tuple[IntegrationStatus, Optional[ValidationIssue]]


class IntegrationValidator:
    """Validates the wiring between platform subsystems (read-only, no execution).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``integration_statuses`` reports each integration
    point as an :class:`IntegrationStatus`; ``validate`` folds them into a single
    :class:`ValidationResult`. It reads the DI graph and health surface only — it
    exercises no interaction and runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def integration_statuses(self) -> List[IntegrationStatus]:
        """Return an :class:`IntegrationStatus` for each validated integration point."""
        return [status for status, _ in self._checks()]

    def validate(self) -> ValidationResult:
        """Return the aggregate integration :class:`ValidationResult`."""
        checks = self._checks()
        issues = [issue for _, issue in checks if issue is not None]
        connected = sum(1 for status, _ in checks if status.connected)
        return common.result(
            name="subsystem integration",
            scope=ValidationScope.INTEGRATION,
            issues=issues,
            detail=f"{connected}/{len(checks)} integrations connected",
            metadata={"integration_count": len(checks)},
        )

    # --- checks ----------------------------------------------------------
    def _checks(self) -> List[_Check]:
        """Return every integration check as a (status, optional-issue) pair."""
        health = self._component_health()
        service = self.operations.service
        ai_employee = getattr(service, "ai_employee", None)
        return [
            self._planning_runtime(ai_employee),
            self._runtime_capabilities(ai_employee),
            self._aiemployee_service(service, ai_employee),
            self._service_operations(service),
            self._health_pair("Memory <-> Persistence", "memory",
                               "persistence", health),
            self._health_pair("Scheduler <-> Recovery", "scheduler",
                              "recovery", health),
            self._approval_notification(),
        ]

    def _planning_runtime(self, ai_employee) -> _Check:
        """Planning ↔ Runtime: both collaborators wired into the AI Employee."""
        planning = getattr(ai_employee, "planning_engine", None) is not None
        runtime = (
            getattr(ai_employee, "workflow_coordinator", None) is not None
        )
        connected = planning and runtime
        return self._wired(
            "Planning <-> Runtime", "planning", "runtime", connected
        )

    def _runtime_capabilities(self, ai_employee) -> _Check:
        """Runtime ↔ Capabilities: the Runtime host that executes capabilities."""
        connected = (
            getattr(ai_employee, "workflow_coordinator", None) is not None
        )
        return self._wired(
            "Runtime <-> Capabilities", "runtime", "capabilities", connected
        )

    def _aiemployee_service(self, service, ai_employee) -> _Check:
        """AIEmployee ↔ Service: the service delegates to a wired AI Employee."""
        connected = ai_employee is not None and hasattr(
            ai_employee, "delegate"
        )
        return self._wired(
            "AIEmployee <-> Service", "ai_employee", "service", connected
        )

    def _service_operations(self, service) -> _Check:
        """Service ↔ Operations: observability shares the single service instance."""
        shared = getattr(self.operations.observability, "service", None)
        connected = shared is not None
        consistent = shared is service
        status = IntegrationStatus(
            name="Service <-> Operations",
            source="service",
            target="operations",
            connected=connected,
            consistent=consistent,
            detail=(
                "shared service instance"
                if consistent
                else "operations does not share the service instance"
            ),
        )
        if not consistent:
            return status, common.issue(
                issue_id="integration-service-operations",
                message="Service <-> Operations is not a shared instance",
                severity=ValidationSeverity.ERROR,
                component="operations",
            )
        return status, None

    def _health_pair(
        self, name: str, source: str, target: str, health: Dict[str, bool]
    ) -> _Check:
        """A health-mapped pair: both subsystems reported and up (warn when down)."""
        connected = source in health and target in health
        consistent = health.get(source, False) and health.get(target, False)
        status = IntegrationStatus(
            name=name,
            source=source,
            target=target,
            connected=connected,
            consistent=consistent,
            detail="both healthy" if consistent else "a side is not healthy",
        )
        if not connected:
            return status, common.issue(
                issue_id=f"integration-{source}-{target}",
                message=f"integration not reported: {name}",
                severity=ValidationSeverity.ERROR,
                component=name,
            )
        if not consistent:
            return status, common.issue(
                issue_id=f"integration-{source}-{target}",
                message=f"integration side unhealthy: {name}",
                severity=ValidationSeverity.WARNING,
                component=name,
            )
        return status, None

    def _approval_notification(self) -> _Check:
        """Approval ↔ Notification: both engine modules integrate and expose coordinators."""
        connected = True
        detail = "both coordinators available"
        try:
            import app.services.ai_employee.approval as approval_pkg
            import app.services.ai_employee.notification as notification_pkg

            connected = hasattr(
                approval_pkg, "ApprovalWorkflowCoordinator"
            ) and hasattr(
                notification_pkg, "NotificationWorkflowCoordinator"
            )
            if not connected:
                detail = "a coordinator export is missing"
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            connected = False
            detail = f"import failed: {exc.__class__.__name__}"
        status = IntegrationStatus(
            name="Approval <-> Notification",
            source="approval",
            target="notification",
            connected=connected,
            consistent=connected,
            detail=detail,
        )
        if not connected:
            return status, common.issue(
                issue_id="integration-approval-notification",
                message="Approval <-> Notification is not integrated",
                severity=ValidationSeverity.ERROR,
                component="approval",
                detail=detail,
            )
        return status, None

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _wired(
        name: str, source: str, target: str, connected: bool
    ) -> _Check:
        """Build a structural-wiring check; an unwired integration is a blocker."""
        status = IntegrationStatus(
            name=name,
            source=source,
            target=target,
            connected=connected,
            consistent=connected,
            detail="wired" if connected else "not wired",
        )
        if not connected:
            return status, common.issue(
                issue_id=f"integration-{source}-{target}",
                message=f"integration not wired: {name}",
                severity=ValidationSeverity.ERROR,
                component=name,
            )
        return status, None

    def _component_health(self) -> Dict[str, bool]:
        """Return the subsystem -> healthy map from the operations observability."""
        return {
            component.name: component.healthy
            for component in self.operations.observability.component_status()
        }
