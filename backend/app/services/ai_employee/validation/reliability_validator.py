"""Reliability validator (Sprint 16.13 — validate platform reliability by reading state).

Defines :class:`ReliabilityValidator`, which validates the platform's reliability by
*reading* the frozen Sprint 16.11 :class:`EnterpriseOperationsManager`. It checks
recovery readiness, workflow consistency (task-state counters reconcile), determinism
(a repeated read yields an identical result), state consistency (session/task
invariants hold), and dependency integrity (every required dependency is ready).

Each check is a deterministic read of platform state — it exercises no recovery, runs
no workflow, and changes no behaviour. It observes only: it validates and executes,
delegates, and stores nothing. Strictly additive to Sprints 1.x–16.12, whose modules
are left untouched.
"""

from typing import Dict

from app.services.ai_employee.validation import common
from app.services.ai_employee.validation.models import (
    ReliabilitySummary,
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
)

# Per-state task counters the workflow-consistency check reconciles against the total.
_STATE_KEYS = (
    "tasks_running",
    "tasks_paused",
    "tasks_completed",
    "tasks_failed",
    "tasks_cancelled",
)


class ReliabilityValidator:
    """Validates platform reliability from read-only state checks (no execution).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``summary`` runs the five deterministic checks
    into a :class:`ReliabilitySummary`; ``validate`` folds them into a
    :class:`ValidationResult`. It reads platform state only — it exercises no recovery
    and runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def summary(self) -> ReliabilitySummary:
        """Return the :class:`ReliabilitySummary` of the five reliability checks."""
        recovery_ready = self._recovery_ready()
        workflow_consistent = self._workflow_consistent()
        deterministic = self._deterministic()
        state_consistent = self._state_consistent()
        dependency_integrity = self._dependency_integrity()
        reliable = all(
            (
                recovery_ready,
                workflow_consistent,
                deterministic,
                state_consistent,
                dependency_integrity,
            )
        )
        return ReliabilitySummary(
            recovery_ready=recovery_ready,
            workflow_consistent=workflow_consistent,
            deterministic=deterministic,
            state_consistent=state_consistent,
            dependency_integrity=dependency_integrity,
            reliable=reliable,
            detail="reliable" if reliable else "reliability concerns found",
        )

    def validate(self) -> ValidationResult:
        """Return the aggregate reliability :class:`ValidationResult`."""
        summary = self.summary()
        checks = {
            "recovery_ready": summary.recovery_ready,
            "workflow_consistent": summary.workflow_consistent,
            "deterministic": summary.deterministic,
            "state_consistent": summary.state_consistent,
            "dependency_integrity": summary.dependency_integrity,
        }
        issues = [
            common.issue(
                issue_id=f"reliability-{name}",
                message=f"reliability check failed: {name}",
                severity=ValidationSeverity.ERROR,
                component=name,
            )
            for name, ok in checks.items()
            if not ok
        ]
        passed = sum(1 for ok in checks.values() if ok)
        return common.result(
            name="platform reliability",
            scope=ValidationScope.RELIABILITY,
            issues=issues,
            detail=f"{passed}/{len(checks)} reliability checks passed",
            metadata={"checks": checks},
        )

    # --- checks ----------------------------------------------------------
    def _recovery_ready(self) -> bool:
        """Return whether the Recovery subsystem is reported healthy."""
        for component in self.operations.observability.component_status():
            if component.name == "recovery":
                return component.healthy
        return False

    def _workflow_consistent(self) -> bool:
        """Return whether the per-state task counters reconcile with the total."""
        execution = self._execution()
        total = execution.get("tasks_total", 0)
        counted = sum(execution.get(key, 0) for key in _STATE_KEYS)
        return total == counted

    def _deterministic(self) -> bool:
        """Return whether a repeated metrics read yields an identical snapshot.

        The observability manager is a pure read of platform state, so two consecutive
        reads must be equal; any difference would signal hidden mutation.
        """
        first = self.operations.observability.metrics()
        second = self.operations.observability.metrics()
        return first == second

    def _state_consistent(self) -> bool:
        """Return whether the session/task invariants hold (no negative or over-count)."""
        resource = dict(
            self.operations.observability.service_statistics().metrics
        )
        sessions_total = resource.get("sessions_total", 0)
        sessions_active = resource.get("sessions_active", 0)
        execution = self._execution()
        total = execution.get("tasks_total", 0)
        return (
            0 <= sessions_active <= sessions_total
            and total >= 0
            and total == sum(execution.get(key, 0) for key in _STATE_KEYS)
        )

    def _dependency_integrity(self) -> bool:
        """Return whether every required subsystem dependency is ready."""
        return self.operations.deployment.validate_dependencies().ready

    def _execution(self) -> Dict[str, int]:
        """Return the per-state execution counters."""
        return dict(
            self.operations.observability.execution_statistics().metrics
        )
