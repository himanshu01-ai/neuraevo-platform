"""Execution monitor (Sprint 13.12 — deterministic execution observation).

Reasoning-only component that consumes an :class:`ExecutionSchedule` and an
:class:`ExecutionState` and produces a single immutable, provider-independent
:class:`ExecutionMonitoringReport`. It OBSERVES execution: it groups the
schedule's nodes into active, pending, blocked, and completed sets, echoes the
execution state's status and progress, and derives an overall health — but it
never executes, resolves, schedules, or acquires anything, and it never mutates
its inputs.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same inputs in -> same report out.
"""

from typing import List

from app.services.planning.execution_monitor_models import (
    ExecutionHealthStatus,
    ExecutionMonitoringReport,
)
from app.services.planning.execution_schedule_models import ExecutionSchedule
from app.services.planning.execution_state_models import (
    ExecutionState,
    ExecutionStateType,
)


class ExecutionMonitor:
    """Stateless monitor: (schedule, state) -> :class:`ExecutionMonitoringReport`.

    Holds no state and owns no session, provider, or cache. The schedule supplies
    node identity — its scheduled nodes are active, its deferred nodes pending,
    its blocked nodes blocked — while the execution state supplies the aggregate
    status, progress, and the signals that derive health. It observes only; it
    never executes a step and never mutates its inputs.
    """

    def create_report(
        self, schedule: ExecutionSchedule, state: ExecutionState
    ) -> ExecutionMonitoringReport:
        """Return a deterministic :class:`ExecutionMonitoringReport` (no execution).

        The schedule's scheduled/deferred/blocked node ids become the active/
        pending/blocked groups; completed nodes are those the schedule ordered but
        no longer lists in any live group (empty for a forward-looking schedule).
        Progress and status come from the execution state, and health is derived
        from both. Inputs are only read; nothing is executed. An empty schedule
        yields empty node groups — an empty report.
        """
        active_nodes = [node.node_id for node in schedule.scheduled_nodes]
        pending_nodes = list(schedule.deferred_nodes)
        blocked_nodes = list(schedule.blocked_nodes)
        completed_nodes = self._completed(
            schedule, active_nodes, pending_nodes, blocked_nodes
        )

        health = self._health(state, active_nodes, blocked_nodes, pending_nodes)
        warnings = self._warnings(
            state, active_nodes, blocked_nodes, pending_nodes
        )

        return ExecutionMonitoringReport(
            report_id=f"monitor-{state.execution_id}",
            execution_id=state.execution_id,
            execution_status=state.overall_state,
            overall_progress=state.progress_percentage,
            active_nodes=active_nodes,
            blocked_nodes=blocked_nodes,
            completed_nodes=completed_nodes,
            pending_nodes=pending_nodes,
            health_status=health.value,
            warnings=warnings,
            metadata={
                "active_count": len(active_nodes),
                "pending_count": len(pending_nodes),
                "blocked_count": len(blocked_nodes),
                "completed_count": len(completed_nodes),
                "total_tasks": state.total_tasks,
                "scheduling_strategy": schedule.scheduling_strategy,
            },
        )

    @staticmethod
    def _completed(
        schedule: ExecutionSchedule,
        active: List[str],
        pending: List[str],
        blocked: List[str],
    ) -> List[str]:
        """Return ordered nodes no longer live (empty for a valid schedule).

        A node that has completed has left the schedule's scheduled/deferred/
        blocked sets. A forward-looking schedule therefore lists none, so this is
        empty; it surfaces only a node lingering in ``execution_order`` after
        dropping out of every live group.
        """
        live = set(active) | set(pending) | set(blocked)
        return [
            node_id
            for node_id in schedule.execution_order
            if node_id not in live
        ]

    @staticmethod
    def _health(
        state: ExecutionState,
        active: List[str],
        blocked: List[str],
        pending: List[str],
    ) -> ExecutionHealthStatus:
        """Derive the overall :class:`ExecutionHealthStatus` (deterministic).

        Terminal execution states decide first (FAILED/COMPLETED, then a
        cancelled execution is flagged as a warning). Otherwise blocked work with
        nothing active is BLOCKED; blocked work alongside active work — or ready
        work stalled with nothing active — is a WARNING; active work with no
        blockers is HEALTHY; and an idle, unblocked observation is HEALTHY.
        """
        status = state.overall_state
        if status == ExecutionStateType.FAILED.value:
            return ExecutionHealthStatus.FAILED
        if status == ExecutionStateType.COMPLETED.value:
            return ExecutionHealthStatus.COMPLETED
        if status == ExecutionStateType.CANCELLED.value:
            return ExecutionHealthStatus.WARNING
        if blocked and not active:
            return ExecutionHealthStatus.BLOCKED
        if blocked:
            return ExecutionHealthStatus.WARNING
        if active:
            return ExecutionHealthStatus.HEALTHY
        if pending:
            return ExecutionHealthStatus.WARNING
        return ExecutionHealthStatus.HEALTHY

    @staticmethod
    def _warnings(
        state: ExecutionState,
        active: List[str],
        blocked: List[str],
        pending: List[str],
    ) -> List[str]:
        """Build the deterministic, plain-language warning list."""
        warnings: List[str] = []
        if state.overall_state == ExecutionStateType.FAILED.value:
            warnings.append("Execution has failed.")
        elif state.overall_state == ExecutionStateType.CANCELLED.value:
            warnings.append("Execution was cancelled.")
        if blocked:
            warnings.append(
                f"{len(blocked)} node(s) are blocked and cannot proceed."
            )
        if blocked and not active:
            warnings.append("No nodes are active while blocked work remains.")
        if pending and not active:
            warnings.append("Ready nodes are pending but none are active.")
        if (
            state.failed_tasks > 0
            and state.overall_state != ExecutionStateType.FAILED.value
        ):
            warnings.append(f"{state.failed_tasks} task(s) have failed.")
        return warnings
