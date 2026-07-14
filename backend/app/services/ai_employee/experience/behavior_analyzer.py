"""Behavior analyzer (Sprint 16.12 — measure usage behaviour by reading state).

Defines :class:`BehaviorAnalyzer`, which computes deterministic
:class:`BehaviorMetrics` by *reading* observed task state and session state — never by
instrumenting execution. It reports feature usage, capability usage, workflow
frequency, repeat usage (names exercised more than once), and session analytics.

It reads only the public surface of its injected collaborator — the frozen Sprint
16.10 :class:`AIEmployeeService` (via ``list_tasks`` and its ``session_manager``) — or
an explicit observation set passed by the caller. It observes only: it computes and
executes, delegates, and stores nothing, and it never plans or modifies AI behaviour.
Strictly additive to Sprints 1.x–16.11, whose modules are left untouched.
"""

from typing import Callable, Dict, List, Optional

from app.services.ai_employee.experience import signals
from app.services.ai_employee.experience.models import BehaviorMetrics
from app.services.ai_employee.service import (
    AIEmployeeService,
    TaskStatusResponse,
)


class BehaviorAnalyzer:
    """Computes :class:`BehaviorMetrics` by reading observed state (no execution).

    Constructed with an injected :class:`AIEmployeeService` (constructor injection; it
    instantiates none). ``analyze`` aggregates the observed tasks into deterministic
    feature/capability/workflow usage counts, the repeat-usage subset, and the session
    analytics read from the service's session manager. It is stateless and reads only —
    it runs and connects to no external system.
    """

    def __init__(self, service: AIEmployeeService) -> None:
        self.service = service

    def analyze(
        self, tasks: Optional[List[TaskStatusResponse]] = None
    ) -> BehaviorMetrics:
        """Return the :class:`BehaviorMetrics` for the observed tasks and sessions.

        Analyses the supplied ``tasks`` when given, else the service's live task list;
        session analytics always read the service's session manager. Deterministic; it
        runs nothing.
        """
        observed = signals.resolve_tasks(self.service, tasks)
        capability_usage = self._count(observed, signals.capability)
        feature_usage = self._count(observed, signals.feature)
        workflow_frequency = self._count(observed, signals.workflow)
        repeat_usage = {
            name: count
            for name, count in capability_usage.items()
            if count > 1
        }
        total_sessions, active_sessions = self._session_counts()
        return BehaviorMetrics(
            feature_usage=feature_usage,
            capability_usage=capability_usage,
            workflow_frequency=workflow_frequency,
            repeat_usage=repeat_usage,
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            metrics_metadata={"observed_tasks": len(observed)},
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _count(
        tasks: List[TaskStatusResponse],
        selector: Callable[[TaskStatusResponse], str],
    ) -> Dict[str, int]:
        """Return the deterministic usage count of ``selector``'s non-empty values."""
        counts: Dict[str, int] = {}
        for task in tasks:
            name = selector(task)
            if not name:
                continue
            counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items()))

    def _session_counts(self) -> tuple[int, int]:
        """Return the deterministic (total, active) session counts."""
        sessions = self.service.session_manager
        return len(sessions.list()), len(sessions.active())
