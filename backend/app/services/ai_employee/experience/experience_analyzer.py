"""Experience analyzer (Sprint 16.12 — measure task experience by reading state).

Defines :class:`ExperienceAnalyzer`, which computes deterministic
:class:`ExperienceMetrics` by *reading* observed task state — never by instrumenting
execution. It reports task success, workflow completion, average execution size (a
deterministic step-count proxy for duration), approval and recovery rates, and
per-capability success.

It reads only the public surface of its injected collaborator — the frozen Sprint
16.10 :class:`AIEmployeeService` (via ``list_tasks``) — or an explicit observation set
passed by the caller. It observes only: it computes and executes, delegates, and
stores nothing, and it never plans or modifies AI behaviour. Strictly additive to
Sprints 1.x–16.11, whose modules are left untouched.
"""

from typing import Dict, List, Optional

from app.services.ai_employee.experience import signals
from app.services.ai_employee.experience.models import ExperienceMetrics
from app.services.ai_employee.service import (
    AIEmployeeService,
    TaskStatusResponse,
)


class ExperienceAnalyzer:
    """Computes :class:`ExperienceMetrics` by reading observed task state (no execution).

    Constructed with an injected :class:`AIEmployeeService` (constructor injection; it
    instantiates none). ``analyze`` aggregates the observed tasks into deterministic
    success, completion, execution-size, approval, recovery, and per-capability success
    measurements. It is stateless and reads only — it runs and connects to no external
    system.
    """

    def __init__(self, service: AIEmployeeService) -> None:
        self.service = service

    def analyze(
        self, tasks: Optional[List[TaskStatusResponse]] = None
    ) -> ExperienceMetrics:
        """Return the :class:`ExperienceMetrics` for the observed tasks.

        Analyses the supplied ``tasks`` when given, else the service's live task list.
        An empty observation set yields all-zero metrics. Deterministic; it runs
        nothing.
        """
        observed = signals.resolve_tasks(self.service, tasks)
        count = len(observed)
        if count == 0:
            return ExperienceMetrics(task_count=0)

        successes = sum(1 for task in observed if signals.succeeded(task))
        completions = sum(
            1 for task in observed if signals.workflow_completed(task)
        )
        total_units = sum(
            signals.execution_units(task) for task in observed
        )
        approvals = sum(
            1 for task in observed if signals.approval_required(task)
        )
        recoveries = sum(
            1 for task in observed if signals.recovery_required(task)
        )
        return ExperienceMetrics(
            task_count=count,
            task_success_rate=round(successes / count, 4),
            workflow_completion_rate=round(completions / count, 4),
            average_execution_units=round(total_units / count, 4),
            approval_rate=round(approvals / count, 4),
            recovery_rate=round(recoveries / count, 4),
            capability_success=self._capability_success(observed),
            metrics_metadata={
                "successful_tasks": successes,
                "completed_workflows": completions,
            },
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _capability_success(
        tasks: List[TaskStatusResponse],
    ) -> Dict[str, float]:
        """Return each observed capability's success fraction (deterministic order)."""
        totals: Dict[str, int] = {}
        wins: Dict[str, int] = {}
        for task in tasks:
            name = signals.capability(task)
            if not name:
                continue
            totals[name] = totals.get(name, 0) + 1
            if signals.succeeded(task):
                wins[name] = wins.get(name, 0) + 1
        return {
            name: round(wins.get(name, 0) / totals[name], 4)
            for name in sorted(totals)
        }
