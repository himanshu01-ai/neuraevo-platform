"""Scheduler inspector (Sprint 16.14 — visualise scheduling from execution state).

Defines :class:`SchedulerInspector`, which projects the scheduler view of the dashboard
— scheduled workflows, a queue summary, and an execution summary — by *reading* the
frozen Sprint 16.11 :class:`EnterpriseOperationsManager`'s observability and scheduler
health. It never executes a workflow, changes behaviour, or modifies state.

The submitted workflows are the scheduled work; their lifecycle states form the queue
summary (running/paused are pending, the terminal states are done), and the execution
counters form the execution summary. It observes only: it reads and executes,
delegates, and stores nothing. Strictly additive to Sprints 1.x–16.13, whose modules
are left untouched.
"""

from typing import Dict

from app.services.ai_employee.dashboard import common
from app.services.ai_employee.dashboard.models import SchedulerDashboard


class SchedulerInspector:
    """Projects the scheduler dashboard from execution counters (read-only).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``dashboard`` reads the execution statistics and
    scheduler health and reports the scheduled-workflow count, queue summary, and
    execution summary. It is stateless and reads only — it runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def dashboard(self) -> SchedulerDashboard:
        """Return the :class:`SchedulerDashboard` for the scheduling subsystem."""
        component = common.component_map(self.operations).get("scheduler")
        present = component is not None
        healthy = bool(component.healthy) if present else False
        state = component.state.value if present else "UNKNOWN"
        execution: Dict[str, int] = dict(
            self.operations.observability.execution_statistics().metrics
        )
        pending = execution.get("tasks_running", 0) + execution.get(
            "tasks_paused", 0
        )
        return SchedulerDashboard(
            present=present,
            healthy=healthy,
            state=state,
            scheduled_workflows=execution.get("tasks_total", 0),
            queue_summary={
                "pending": pending,
                "completed": execution.get("tasks_completed", 0),
                "failed": execution.get("tasks_failed", 0),
                "cancelled": execution.get("tasks_cancelled", 0),
            },
            execution_summary=execution,
            dashboard_metadata={"source": "operations.observability"},
        )
