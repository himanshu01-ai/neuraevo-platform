"""Recovery manager (Sprint 13.13 — deterministic recovery planning).

Reasoning-only component that consumes an :class:`ExecutionMonitoringReport`, an
:class:`ExecutionState`, and an :class:`ExecutionDependencyGraph` and produces a
single immutable, provider-independent :class:`RecoveryPlan`. It PLANS recovery:
it reads the observed health, identifies the affected nodes, partitions them into
recoverable and unrecoverable, selects a strategy, and decides whether a human
must step in — but it never retries, resumes, executes, resolves, or acquires
anything, and it never mutates its inputs.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same inputs in -> same plan out.
"""

from typing import List, Tuple

from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
)
from app.services.planning.execution_monitor_models import (
    ExecutionHealthStatus,
    ExecutionMonitoringReport,
)
from app.services.planning.execution_state_models import ExecutionState
from app.services.planning.recovery_models import RecoveryPlan, RecoveryStrategy

# Recovery reasons per outcome (plain language, no implementation terms).
_REASON_EMPTY = "Execution has no nodes to recover; no action is required."
_REASON_HEALTHY = "Execution is healthy; no recovery action is required."
_REASON_COMPLETED = "Execution has completed; no recovery action is required."
_REASON_PROGRESSING = (
    "Execution is progressing; no recovery action is required."
)
_REASON_RETRY = (
    "Execution failed but recoverable work remains; retrying the affected "
    "nodes."
)
_REASON_ABORT = "Execution failed with no recoverable path; aborting."
_REASON_RESUME = (
    "Execution is blocked but an executable path remains; resuming from the "
    "ready work."
)
_REASON_REPLAN = (
    "Execution is blocked by a dependency deadlock or cycle; replanning is "
    "required."
)


class RecoveryManager:
    """Stateless manager: (report, state, graph) -> :class:`RecoveryPlan`.

    Holds no state and owns no session, provider, or cache. The report supplies
    the observed health and the impacted node ids, the graph supplies the
    structural facts (a remaining executable path, a dependency cycle), and the
    state supplies the execution identity. It plans only; it never retries,
    resumes, or executes a step, and never mutates its inputs.
    """

    def create_recovery_plan(
        self,
        report: ExecutionMonitoringReport,
        state: ExecutionState,
        graph: ExecutionDependencyGraph,
    ) -> RecoveryPlan:
        """Return a deterministic :class:`RecoveryPlan` (no execution).

        Selects a strategy from the observed health and the graph's structure: a
        healthy, complete, or empty execution needs no action; a failed execution
        retries when recoverable work remains and aborts otherwise; a blocked
        execution resumes when an executable path remains and replans on a
        deadlock or cycle. The affected nodes are split into recoverable and
        unrecoverable by whether a forward path exists. Inputs are only read.
        """
        forward_path = bool(graph.ready_nodes) and not graph.has_cycles
        affected = self._ordered(
            graph, set(report.blocked_nodes) | set(report.active_nodes)
        )
        recoverable = affected if forward_path else []
        unrecoverable = [] if forward_path else affected

        strategy, reason = self._select(report, graph, recoverable, forward_path)

        # NO_ACTION means there is nothing to recover — clear the impact sets so
        # the plan cannot both claim "no action" and list affected work.
        if strategy is RecoveryStrategy.NO_ACTION:
            affected, recoverable, unrecoverable = [], [], []

        requires_intervention = strategy in (
            RecoveryStrategy.REPLAN,
            RecoveryStrategy.ABORT,
        )

        return RecoveryPlan(
            recovery_id=f"recovery-{state.execution_id}",
            execution_id=state.execution_id,
            recovery_strategy=strategy.value,
            affected_nodes=affected,
            recoverable_nodes=recoverable,
            unrecoverable_nodes=unrecoverable,
            requires_user_intervention=requires_intervention,
            recovery_reason=reason,
            metadata={
                "health_status": report.health_status,
                "execution_state": state.overall_state,
                "affected_count": len(affected),
                "recoverable_count": len(recoverable),
                "unrecoverable_count": len(unrecoverable),
                "has_cycles": graph.has_cycles,
                "executable_path": bool(graph.ready_nodes),
            },
        )

    @staticmethod
    def _select(
        report: ExecutionMonitoringReport,
        graph: ExecutionDependencyGraph,
        recoverable: List[str],
        forward_path: bool,
    ) -> Tuple[RecoveryStrategy, str]:
        """Choose the (strategy, reason) pair deterministically.

        Empty executions and healthy/complete/progressing observations need no
        action. A failed execution retries when recoverable nodes remain and
        aborts otherwise; a blocked execution resumes when a forward path remains
        and replans on a deadlock or cycle. Any other health is treated as still
        progressing (no action).
        """
        if not graph.nodes:
            return RecoveryStrategy.NO_ACTION, _REASON_EMPTY

        health = report.health_status
        if health == ExecutionHealthStatus.HEALTHY.value:
            return RecoveryStrategy.NO_ACTION, _REASON_HEALTHY
        if health == ExecutionHealthStatus.COMPLETED.value:
            return RecoveryStrategy.NO_ACTION, _REASON_COMPLETED
        if health == ExecutionHealthStatus.FAILED.value:
            if recoverable:
                return RecoveryStrategy.RETRY, _REASON_RETRY
            return RecoveryStrategy.ABORT, _REASON_ABORT
        if health == ExecutionHealthStatus.BLOCKED.value:
            if forward_path:
                return RecoveryStrategy.RESUME, _REASON_RESUME
            return RecoveryStrategy.REPLAN, _REASON_REPLAN
        # WARNING or any other transitional health: still progressing.
        return RecoveryStrategy.NO_ACTION, _REASON_PROGRESSING

    @staticmethod
    def _ordered(
        graph: ExecutionDependencyGraph, wanted: set
    ) -> List[str]:
        """Return ``wanted`` node ids in canonical graph order (deterministic)."""
        return [node.node_id for node in graph.nodes if node.node_id in wanted]
