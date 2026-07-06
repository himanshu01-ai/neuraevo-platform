"""Execution scheduler (Sprint 13.11 — deterministic schedule construction).

Reasoning-only component that consumes an :class:`ExecutionDependencyGraph` and
an :class:`ExecutionState` and produces a single immutable, provider-independent
:class:`ExecutionSchedule`. It determines what *could* run next: it selects the
schedulable (ready) nodes, defers the rest by ordering, keeps blocked nodes
blocked, and computes a deterministic execution order — but it never executes,
resolves, or acquires anything, and it never mutates its inputs.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same inputs in -> same schedule
out.
"""

from typing import List

from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
)
from app.services.planning.execution_schedule_models import (
    ExecutionSchedule,
    ScheduledNode,
    SchedulingStrategy,
)
from app.services.planning.execution_state_models import ExecutionState

_VALID_STRATEGIES = frozenset(
    strategy.value for strategy in SchedulingStrategy
)


class ExecutionScheduler:
    """Stateless scheduler: (graph, state) -> :class:`ExecutionSchedule`.

    Holds no state and owns no session, provider, or cache. Only ``READY`` graph
    nodes may be scheduled; the strategy (from the graph metadata when available,
    else ``SEQUENTIAL``) decides how many run now versus are deferred; blocked
    nodes stay blocked. It never executes a step and never mutates its inputs.
    """

    def create_schedule(
        self, graph: ExecutionDependencyGraph, state: ExecutionState
    ) -> ExecutionSchedule:
        """Return a deterministic :class:`ExecutionSchedule` (no execution).

        Ready graph nodes (in graph order) are split into scheduled and deferred
        by the resolved strategy; blocked nodes are carried through. The
        execution order is the scheduled node ids in priority order. Inputs are
        only read.
        """
        strategy = self._resolve_strategy(graph)
        node_by_id = {node.node_id: node for node in graph.nodes}
        ready_ids = list(graph.ready_nodes)

        scheduled_ids, deferred_ids = self._split(ready_ids, strategy)

        scheduled_nodes = [
            ScheduledNode(
                node_id=node_id,
                execution_unit_id=node_by_id[node_id].execution_unit_id,
                priority=index + 1,
                scheduled=True,
                reason="Ready and selected for execution.",
                metadata={"strategy": strategy},
            )
            for index, node_id in enumerate(scheduled_ids)
        ]

        return ExecutionSchedule(
            schedule_id=f"schedule-{state.execution_id}",
            execution_id=state.execution_id,
            scheduled_nodes=scheduled_nodes,
            deferred_nodes=deferred_ids,
            blocked_nodes=list(graph.blocked_nodes),
            execution_order=list(scheduled_ids),
            scheduling_strategy=strategy,
            metadata={
                "strategy": strategy,
                "scheduled_count": len(scheduled_ids),
                "deferred_count": len(deferred_ids),
            },
        )

    @staticmethod
    def _resolve_strategy(graph: ExecutionDependencyGraph) -> str:
        """Follow the workflow strategy from graph metadata, else SEQUENTIAL."""
        raw = graph.metadata.get("scheduling_strategy") or graph.metadata.get(
            "execution_mode"
        )
        if raw in _VALID_STRATEGIES:
            return raw
        return SchedulingStrategy.SEQUENTIAL.value

    @staticmethod
    def _split(ready_ids: List[str], strategy: str):
        """Split ready node ids into (scheduled, deferred) by ``strategy``."""
        if not ready_ids:
            return [], []
        if strategy == SchedulingStrategy.PARALLEL.value:
            return list(ready_ids), []
        if strategy == SchedulingStrategy.HYBRID.value:
            cut = (len(ready_ids) + 1) // 2
            return ready_ids[:cut], ready_ids[cut:]
        # SEQUENTIAL: schedule only the first, defer the rest.
        return ready_ids[:1], ready_ids[1:]
