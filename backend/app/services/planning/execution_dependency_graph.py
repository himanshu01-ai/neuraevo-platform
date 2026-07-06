"""Execution dependency graph builder (Sprint 13.10 — deterministic graph).

Reasoning-only component that transforms an :class:`ExecutionQueue` and its
:class:`TaskLifecycle` list into a single immutable, provider-independent
:class:`ExecutionDependencyGraph`. It models task relationships only: it turns
each unit into a node, dependencies into directed edges, derives root/leaf/ready/
blocked sets, and detects cycles — but it never executes, resolves, or acquires
anything, and it never mutates the queue or lifecycles.

Fully deterministic and offline: no AI, network, SDK, Runtime, Session, Registry,
Permission, Tool framework, Memory, or Gemini. Same inputs in -> same graph out.
"""

import hashlib
from typing import Dict, List

from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
    ExecutionEdge,
    ExecutionNode,
)
from app.services.planning.execution_queue_models import ExecutionQueue
from app.services.planning.task_lifecycle_models import (
    TaskLifecycle,
    TaskLifecycleState,
)


class ExecutionDependencyGraphBuilder:
    """Stateless builder: (queue, lifecycles) -> :class:`ExecutionDependencyGraph`.

    Holds no state and owns no session, provider, or cache. It preserves the
    queue's dependency relationships and ordering, computes derived structure
    deterministically, and detects cycles. It never executes a step and never
    mutates the queue or lifecycles.
    """

    def build_graph(
        self, queue: ExecutionQueue, lifecycles: List[TaskLifecycle]
    ) -> ExecutionDependencyGraph:
        """Return a deterministic :class:`ExecutionDependencyGraph` (no execution).

        Every execution unit becomes exactly one node; dependencies become
        directed edges; roots have no dependencies, leaves no dependents; a node
        is ready only when its lifecycle is ``READY`` and every dependency is
        ``COMPLETED``. An empty queue yields an empty graph. Inputs are only
        read.
        """
        units = queue.execution_units
        unit_by_step = {unit.step_number: unit for unit in units}
        lifecycle_state_by_unit = {
            lifecycle.unit_id: lifecycle.current_state
            for lifecycle in lifecycles
        }
        node_id_of = {
            unit.step_number: f"node-{unit.step_number}" for unit in units
        }

        dependents: Dict[int, List[str]] = {
            unit.step_number: [] for unit in units
        }
        for unit in units:
            for dependency in unit.dependencies:
                if dependency in dependents:
                    dependents[dependency].append(
                        node_id_of[unit.step_number]
                    )

        nodes: List[ExecutionNode] = []
        edges: List[ExecutionEdge] = []
        dependency_map: Dict[str, List[str]] = {}
        for unit in units:
            node_id = node_id_of[unit.step_number]
            known_deps = [
                dep for dep in unit.dependencies if dep in node_id_of
            ]
            dependency_node_ids = [node_id_of[dep] for dep in known_deps]
            dependency_map[node_id] = dependency_node_ids

            for dependency in known_deps:
                edges.append(
                    ExecutionEdge(
                        source_node=node_id_of[dependency],
                        target_node=node_id,
                    )
                )

            ready = self._is_ready(
                unit, known_deps, unit_by_step, lifecycle_state_by_unit
            )
            nodes.append(
                ExecutionNode(
                    node_id=node_id,
                    execution_unit_id=unit.unit_id,
                    dependencies=dependency_node_ids,
                    dependents=dependents[unit.step_number],
                    ready=ready,
                    blocked=not ready,
                    metadata={
                        "step_number": unit.step_number,
                        "lifecycle_state": lifecycle_state_by_unit.get(
                            unit.unit_id
                        ),
                    },
                )
            )

        return ExecutionDependencyGraph(
            graph_id=self._graph_id(node_id_of),
            nodes=nodes,
            edges=edges,
            root_nodes=[n.node_id for n in nodes if not n.dependencies],
            leaf_nodes=[n.node_id for n in nodes if not n.dependents],
            ready_nodes=[n.node_id for n in nodes if n.ready],
            blocked_nodes=[n.node_id for n in nodes if n.blocked],
            has_cycles=self._has_cycles(dependency_map),
            metadata={"node_count": len(nodes), "edge_count": len(edges)},
        )

    @staticmethod
    def _is_ready(
        unit,
        known_deps: List[int],
        unit_by_step: dict,
        lifecycle_state_by_unit: Dict[str, str],
    ) -> bool:
        """A node is ready only when its lifecycle is READY and all deps done."""
        own_state = lifecycle_state_by_unit.get(unit.unit_id)
        if own_state != TaskLifecycleState.READY.value:
            return False
        for dependency in known_deps:
            dependency_unit = unit_by_step[dependency]
            dep_state = lifecycle_state_by_unit.get(dependency_unit.unit_id)
            if dep_state != TaskLifecycleState.COMPLETED.value:
                return False
        return True

    @staticmethod
    def _has_cycles(dependency_map: Dict[str, List[str]]) -> bool:
        """Deterministic cycle detection over the dependency relation (DFS)."""
        white, gray, black = 0, 1, 2
        color = {node: white for node in dependency_map}

        def visit(node: str) -> bool:
            color[node] = gray
            for dependency in dependency_map.get(node, []):
                dependency_color = color.get(dependency, black)
                if dependency_color == gray:
                    return True
                if dependency_color == white and visit(dependency):
                    return True
            color[node] = black
            return False

        for node in dependency_map:
            if color[node] == white and visit(node):
                return True
        return False

    @staticmethod
    def _graph_id(node_id_of: Dict[int, str]) -> str:
        """Derive a stable, deterministic id from the ordered node ids."""
        raw = "|".join(node_id_of[step] for step in sorted(node_id_of))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"graph-{digest}"
