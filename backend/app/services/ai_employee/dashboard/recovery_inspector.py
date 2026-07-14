"""Recovery inspector (Sprint 16.14 — visualise recovery from audit and execution).

Defines :class:`RecoveryInspector`, which projects the recovery view of the dashboard —
recovery history, retry statistics, and a failure summary — by *reading* the frozen
Sprint 16.11 :class:`EnterpriseOperationsManager`'s recovery-category audit records,
execution counters, and recovery health. It never executes a workflow, changes
behaviour, or modifies state.

The audit trail's ``RECOVERY`` records form the recovery history; the failed-task
counter and recovery-event count form the retry/failure summaries. It observes only: it
reads and executes, delegates, and stores nothing. Strictly additive to Sprints
1.x–16.13, whose modules are left untouched.
"""

from typing import Any, Dict, List

from app.services.ai_employee.dashboard import common
from app.services.ai_employee.dashboard.models import RecoveryDashboard
from app.services.ai_employee.operations import AuditCategory, AuditQuery


class RecoveryInspector:
    """Projects the recovery dashboard from audit + execution state (read-only).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``dashboard`` reads the recovery-category audit
    records, execution counters, and recovery health and reports the recovery history,
    retry statistics, and failure summary. It is stateless and reads only — it runs
    nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def dashboard(self) -> RecoveryDashboard:
        """Return the :class:`RecoveryDashboard` for the recovery subsystem."""
        component = common.component_map(self.operations).get("recovery")
        present = component is not None
        healthy = bool(component.healthy) if present else False
        state = component.state.value if present else "UNKNOWN"
        records = self.operations.audit(
            AuditQuery(category=AuditCategory.RECOVERY)
        )
        history: List[Dict[str, Any]] = [
            {
                "record_id": record.record_id,
                "action": record.action,
                "resource": record.resource,
                "outcome": record.outcome,
                "sequence": record.sequence,
            }
            for record in records
        ]
        execution: Dict[str, int] = dict(
            self.operations.observability.execution_statistics().metrics
        )
        failed = execution.get("tasks_failed", 0)
        return RecoveryDashboard(
            present=present,
            healthy=healthy,
            state=state,
            recovery_history=history,
            retry_statistics={
                "recovery_events": len(history),
                "failed_tasks": failed,
            },
            failure_summary={
                "failed_tasks": failed,
                "recovery_events": len(history),
            },
            dashboard_metadata={"source": "operations.audit"},
        )
