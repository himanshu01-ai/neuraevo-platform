"""Workflow inspector (Sprint 16.14 — visualise workflow state from the service).

Defines :class:`WorkflowInspector`, which projects the workflow view of the dashboard —
workflow status, history, lifecycle state, and progress — by *reading* the frozen
Sprint 16.10 :class:`AIEmployeeService`'s task list. It never executes a workflow,
changes behaviour, or modifies state.

Each task the service tracks is one workflow engagement; the inspector reads its state,
its recorded workflow status, and its success into a deterministic
:class:`WorkflowDashboard`. It observes only: it reads and executes, delegates, and
stores nothing. Strictly additive to Sprints 1.x–16.13, whose modules are left
untouched.
"""

from typing import Any, Dict, List

from app.services.ai_employee.dashboard.models import WorkflowDashboard
from app.services.ai_employee.service import TaskState


class WorkflowInspector:
    """Projects the workflow dashboard from the service task list (read-only).

    Constructed with an injected :class:`AIEmployeeService` (constructor injection; it
    instantiates none). ``dashboard`` reads the tracked tasks and reports their status
    counts, history, and progress. It is stateless and reads only — it runs nothing.
    """

    def __init__(self, service) -> None:
        self.service = service

    def dashboard(self) -> WorkflowDashboard:
        """Return the :class:`WorkflowDashboard` for the observed workflows."""
        tasks = self.service.list_tasks()
        total = len(tasks)
        status_counts: Dict[str, int] = {
            state.value: 0 for state in TaskState
        }
        history: List[Dict[str, Any]] = []
        completed = 0
        for task in tasks:
            state_label = task.state.value if task.state else "UNKNOWN"
            status_counts[state_label] = status_counts.get(state_label, 0) + 1
            if task.success:
                completed += 1
            history.append(
                {
                    "task_id": task.task_id,
                    "state": state_label,
                    "success": task.success,
                    "workflow_status": task.result_summary.get(
                        "workflow_status", ""
                    ),
                }
            )
        progress = {
            "total": float(total),
            "completed": float(completed),
            "completion_rate": (
                round(completed / total, 4) if total else 0.0
            ),
        }
        return WorkflowDashboard(
            total=total,
            status_counts=status_counts,
            history=history,
            progress=progress,
            dashboard_metadata={"source": "ai_employee_service"},
        )
