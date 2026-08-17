"""Observability manager (Sprint 16.11 — collect deterministic operational telemetry).

Defines :class:`ObservabilityManager`, which collects deterministic operational
telemetry by *reading* platform state — never by instrumenting execution. It reports
``metrics`` (aggregate counters), ``component_status`` (per-subsystem health),
``execution_statistics`` (task-state counters), and ``service_statistics``
(session/audit counters), each as an immutable DTO.

It reads only the public surfaces of its injected collaborators — the frozen Sprint
16.10 :class:`AIEmployeeService`, the frozen Sprint 16.10 :class:`HealthManager`, and
the Sprint 16.11 :class:`AuditManager` — and connects to no external telemetry
system (no Prometheus, no OpenTelemetry). It is deterministic and stateless: it
collects only and executes, delegates, and stores nothing. Strictly additive to
Sprints 1.x–16.10, whose modules are left untouched.
"""

from typing import Dict, List

from app.services.ai_employee.operations.audit import AuditManager
from app.services.ai_employee.operations.models import (
    ComponentStatus,
    MetricSnapshot,
)
from app.services.ai_employee.service import (
    AIEmployeeService,
    HealthManager,
    HealthState,
    TaskState,
)


class ObservabilityManager:
    """Collects deterministic telemetry by reading platform state (no instrumentation).

    Constructed with an injected :class:`AIEmployeeService`, :class:`HealthManager`,
    and :class:`AuditManager` (constructor injection; it instantiates none). ``metrics``
    aggregates every counter; ``execution_statistics`` counts tasks by state;
    ``service_statistics`` counts sessions and audit records; and ``component_status``
    projects the health report into per-subsystem :class:`ComponentStatus`\\ es. It is
    stateless and reads only — it runs and connects to no external system.
    """

    def __init__(
        self,
        service: AIEmployeeService,
        health_manager: HealthManager,
        audit_manager: AuditManager,
    ) -> None:
        self.service = service
        self.health_manager = health_manager
        self.audit_manager = audit_manager

    # --- metrics ---------------------------------------------------------
    def metrics(self) -> MetricSnapshot:
        """Return an aggregate :class:`MetricSnapshot` of every operational counter."""
        combined: Dict[str, int] = {}
        combined.update(self._task_counts())
        combined.update(self._session_counts())
        combined["audit_records"] = len(self.audit_manager.history())
        return MetricSnapshot(name="metrics", metrics=combined)

    def execution_statistics(self) -> MetricSnapshot:
        """Return a :class:`MetricSnapshot` of task/execution counters."""
        return MetricSnapshot(name="execution", metrics=self._task_counts())

    def service_statistics(self) -> MetricSnapshot:
        """Return a :class:`MetricSnapshot` of session/service counters."""
        metrics = self._session_counts()
        metrics["tasks_total"] = len(self.service.list_tasks())
        metrics["audit_records"] = len(self.audit_manager.history())
        return MetricSnapshot(name="service", metrics=metrics)

    # --- component status ------------------------------------------------
    def component_status(self) -> List[ComponentStatus]:
        """Return the per-subsystem :class:`ComponentStatus` from the health report."""
        health = self.health_manager.health()
        statuses: List[ComponentStatus] = []
        for name, state_value in health.components.items():
            state = HealthState(state_value)
            statuses.append(
                ComponentStatus(
                    name=name,
                    state=state,
                    healthy=state == HealthState.HEALTHY,
                    detail=state.value,
                )
            )
        return statuses

    # --- helpers ---------------------------------------------------------
    def _task_counts(self) -> Dict[str, int]:
        """Return deterministic task counts, total and per :class:`TaskState`."""
        tasks = self.service.list_tasks()
        counts: Dict[str, int] = {"tasks_total": len(tasks)}
        for state in TaskState:
            counts[f"tasks_{state.value.lower()}"] = sum(
                1 for task in tasks if task.state == state
            )
        return counts

    def _session_counts(self) -> Dict[str, int]:
        """Return deterministic session counts (total and active)."""
        sessions = self.service.session_manager
        return {
            "sessions_total": len(sessions.list()),
            "sessions_active": len(sessions.active()),
        }
