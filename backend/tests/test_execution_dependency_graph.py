"""Unit tests for the Sprint 13.10 Execution Dependency Graph.

Covers the additive dependency-graph layer end to end without touching any
network, SDK, AI, tool execution, permission check, registry, runtime, memory, or
database:

* the immutable :class:`ExecutionDependencyGraph` / :class:`ExecutionNode` /
  :class:`ExecutionEdge` DTOs (defaults, immutability, JSON round-trip);
* the deterministic :class:`ExecutionDependencyGraphBuilder` (node/edge
  construction, root/leaf/ready/blocked derivation, cycle detection, empty graph,
  determinism, statelessness, input non-mutation);
* the extended :class:`PlanValidator` (``validate_execution_dependency_graph``);
* the extended :class:`PlanningExplanationBuilder`
  (``build_with_execution_dependency_graph``);
* the extended :class:`PlanningEngine` (``create_execution_dependency_graph`` +
  backward-compatible injection alongside the 13.2–13.9 collaborators);
* the composition-root wiring (``get_execution_dependency_graph_builder``); and
* regression that Sprint 13.1–13.9 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_dependency_graph
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.services.planning import (
    HeuristicPlanningProvider,
    PlanningEngine,
    PlanningExplanationBuilder,
    PlanningRequest,
    PlanValidationError,
    PlanValidator,
)
from app.services.planning.decision_engine import DecisionEngine
from app.services.planning.execution_coordinator import ExecutionCoordinator
from app.services.planning.execution_dependency_graph import (
    ExecutionDependencyGraphBuilder,
)
from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
    ExecutionEdge,
    ExecutionNode,
)
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnit,
)
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine
from app.services.planning.task_lifecycle_models import (
    TASK_LIFECYCLE_TRANSITIONS,
    TERMINAL_TASK_STATES,
    TaskLifecycle,
)


# =====================================================================
# Helpers
# =====================================================================
def _unit(step_number, dependencies, status="READY"):
    return ExecutionUnit(
        unit_id=f"u{step_number}",
        step_number=step_number,
        description=f"Step {step_number}",
        execution_group=1,
        status=status,
        dependencies=dependencies,
    )


def _lc(unit_id, state):
    return TaskLifecycle(
        unit_id=unit_id,
        current_state=state,
        previous_state=None,
        allowed_next_states=list(TASK_LIFECYCLE_TRANSITIONS[state]),
        is_terminal=state in TERMINAL_TASK_STATES,
        state_history=[state],
        metadata={},
    )


def _queue(units):
    return ExecutionQueue(
        queue_id="q",
        workflow_id="wf",
        status="READY",
        execution_units=units,
        total_units=len(units),
        ready_units=0,
        blocked_units=0,
        metadata={},
    )


def _build(units, lifecycles):
    return ExecutionDependencyGraphBuilder().build_graph(
        _queue(units), lifecycles
    )


def _node(node_id, deps=None, dependents=None, ready=True):
    return ExecutionNode(
        node_id=node_id,
        execution_unit_id=f"unit-{node_id}",
        dependencies=deps or [],
        dependents=dependents or [],
        ready=ready,
        blocked=not ready,
        metadata={},
    )


def _graph(**overrides):
    nodes = overrides.pop(
        "nodes",
        [
            _node("node-1", dependents=["node-2"], ready=True),
            _node("node-2", deps=["node-1"], ready=False),
        ],
    )
    data = dict(
        graph_id="graph-1",
        nodes=nodes,
        edges=[ExecutionEdge(source_node="node-1", target_node="node-2")],
        root_nodes=[n.node_id for n in nodes if not n.dependencies],
        leaf_nodes=[n.node_id for n in nodes if not n.dependents],
        ready_nodes=[n.node_id for n in nodes if n.ready],
        blocked_nodes=[n.node_id for n in nodes if n.blocked],
        has_cycles=False,
        metadata={},
    )
    data.update(overrides)
    return ExecutionDependencyGraph(**data)


def _full_engine():
    return PlanningEngine(
        HeuristicPlanningProvider(),
        PlanValidator(),
        PlanningExplanationBuilder(),
        PlanAnalyzer(),
        ExecutionPreparationEngine(),
        DecisionEngine(),
        ExecutionIntentEngine(),
        ExecutionOrchestrator(),
        ExecutionCoordinator(),
        TaskLifecycleEngine(),
        ExecutionStateManager(),
        ExecutionDependencyGraphBuilder(),
    )


_CHAIN = [_unit(1, []), _unit(2, [1]), _unit(3, [2])]


# =====================================================================
# DTOs
# =====================================================================
class GraphModelTests(unittest.TestCase):
    def test_graph_defaults(self):
        graph = ExecutionDependencyGraph(graph_id="g1", has_cycles=False)
        self.assertEqual(graph.nodes, [])
        self.assertEqual(graph.edges, [])
        self.assertEqual(graph.root_nodes, [])

    def test_node_defaults(self):
        node = ExecutionNode(
            node_id="n1", execution_unit_id="u1", ready=True, blocked=False
        )
        self.assertEqual(node.dependencies, [])
        self.assertEqual(node.dependents, [])

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionDependencyGraph(graph_id="g1")  # has_cycles missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _graph().has_cycles = True
        with self.assertRaises(ValidationError):
            _node("n1").ready = False
        with self.assertRaises(ValidationError):
            ExecutionEdge(source_node="a", target_node="b").source_node = "c"

    def test_json_round_trip(self):
        graph = _build(_CHAIN, [_lc("u1", "READY"), _lc("u2", "WAITING"),
                                _lc("u3", "WAITING")])
        restored = ExecutionDependencyGraph.model_validate_json(
            graph.model_dump_json()
        )
        self.assertEqual(restored, graph)


# =====================================================================
# Builder — structure
# =====================================================================
class GraphStructureTests(unittest.TestCase):
    def setUp(self):
        self.lcs = [_lc("u1", "READY"), _lc("u2", "WAITING"), _lc("u3", "WAITING")]
        self.graph = _build(_CHAIN, self.lcs)

    def test_one_node_per_unit(self):
        self.assertEqual(len(self.graph.nodes), 3)
        self.assertEqual(
            {n.node_id for n in self.graph.nodes},
            {"node-1", "node-2", "node-3"},
        )

    def test_nodes_link_units(self):
        first = self.graph.nodes[0]
        self.assertEqual(first.node_id, "node-1")
        self.assertEqual(first.execution_unit_id, "u1")

    def test_dependencies_become_edges(self):
        pairs = {(e.source_node, e.target_node) for e in self.graph.edges}
        self.assertEqual(
            pairs, {("node-1", "node-2"), ("node-2", "node-3")}
        )

    def test_dependencies_and_dependents(self):
        by_id = {n.node_id: n for n in self.graph.nodes}
        self.assertEqual(by_id["node-1"].dependencies, [])
        self.assertEqual(by_id["node-1"].dependents, ["node-2"])
        self.assertEqual(by_id["node-2"].dependencies, ["node-1"])
        self.assertEqual(by_id["node-3"].dependents, [])

    def test_root_and_leaf_nodes(self):
        self.assertEqual(self.graph.root_nodes, ["node-1"])
        self.assertEqual(self.graph.leaf_nodes, ["node-3"])

    def test_graph_id_prefixed_and_deterministic(self):
        other = _build(_CHAIN, self.lcs)
        self.assertTrue(self.graph.graph_id.startswith("graph-"))
        self.assertEqual(self.graph.graph_id, other.graph_id)


# =====================================================================
# Builder — ready / blocked rules
# =====================================================================
class GraphReadinessTests(unittest.TestCase):
    def test_root_ready_only_when_lifecycle_ready(self):
        graph = _build(_CHAIN, [_lc("u1", "READY"), _lc("u2", "WAITING"),
                                _lc("u3", "WAITING")])
        self.assertEqual(graph.ready_nodes, ["node-1"])
        self.assertEqual(set(graph.blocked_nodes), {"node-2", "node-3"})

    def test_root_blocked_when_lifecycle_not_ready(self):
        graph = _build(_CHAIN, [_lc("u1", "WAITING"), _lc("u2", "WAITING"),
                                _lc("u3", "WAITING")])
        self.assertEqual(graph.ready_nodes, [])

    def test_dependent_ready_only_when_dependency_completed(self):
        # node-2 lifecycle READY but node-1 not completed => blocked.
        graph = _build(_CHAIN, [_lc("u1", "WAITING"), _lc("u2", "READY"),
                                _lc("u3", "WAITING")])
        self.assertNotIn("node-2", graph.ready_nodes)

    def test_dependent_ready_when_dependency_completed(self):
        graph = _build(_CHAIN, [_lc("u1", "COMPLETED"), _lc("u2", "READY"),
                                _lc("u3", "WAITING")])
        self.assertEqual(graph.ready_nodes, ["node-2"])

    def test_every_node_ready_xor_blocked(self):
        graph = _build(_CHAIN, [_lc("u1", "READY"), _lc("u2", "WAITING"),
                                _lc("u3", "WAITING")])
        for node in graph.nodes:
            self.assertNotEqual(node.ready, node.blocked)


# =====================================================================
# Builder — cycles, empty, quality
# =====================================================================
class GraphCyclesAndQualityTests(unittest.TestCase):
    def setUp(self):
        self.builder = ExecutionDependencyGraphBuilder()

    def test_acyclic_chain_has_no_cycles(self):
        graph = _build(_CHAIN, [_lc("u1", "READY"), _lc("u2", "WAITING"),
                                _lc("u3", "WAITING")])
        self.assertFalse(graph.has_cycles)

    def test_two_node_cycle_detected(self):
        units = [_unit(1, [2]), _unit(2, [1])]
        graph = _build(units, [_lc("u1", "READY"), _lc("u2", "READY")])
        self.assertTrue(graph.has_cycles)

    def test_three_node_cycle_detected(self):
        units = [_unit(1, [3]), _unit(2, [1]), _unit(3, [2])]
        graph = _build(units, [_lc("u1", "READY"), _lc("u2", "READY"),
                               _lc("u3", "READY")])
        self.assertTrue(graph.has_cycles)

    def test_empty_queue_empty_graph(self):
        graph = _build([], [])
        self.assertEqual(graph.nodes, [])
        self.assertEqual(graph.edges, [])
        self.assertFalse(graph.has_cycles)
        self.assertEqual(graph.root_nodes, [])

    def test_deterministic(self):
        lcs = [_lc("u1", "READY"), _lc("u2", "WAITING"), _lc("u3", "WAITING")]
        self.assertEqual(
            self.builder.build_graph(_queue(_CHAIN), lcs),
            self.builder.build_graph(_queue(_CHAIN), lcs),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.builder), {})

    def test_does_not_mutate_inputs(self):
        queue = _queue(_CHAIN)
        lcs = [_lc("u1", "READY"), _lc("u2", "WAITING"), _lc("u3", "WAITING")]
        before_q = queue.model_dump()
        before_l = [l.model_dump() for l in lcs]
        self.builder.build_graph(queue, lcs)
        self.assertEqual(queue.model_dump(), before_q)
        self.assertEqual([l.model_dump() for l in lcs], before_l)


# =====================================================================
# PlanValidator.validate_execution_dependency_graph
# =====================================================================
class ValidateGraphTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_passes(self):
        self.validator.validate_execution_dependency_graph(_graph())

    def test_empty_graph_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(
                _graph(graph_id="  ")
            )

    def test_duplicate_node_ids_rejected(self):
        graph = _graph(
            nodes=[_node("dup", ready=True), _node("dup", ready=False)],
            root_nodes=["dup"],
            leaf_nodes=["dup"],
            ready_nodes=["dup"],
            blocked_nodes=["dup"],
            edges=[],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(graph)

    def test_node_ready_and_blocked_both_rejected(self):
        bad = ExecutionNode.model_construct(
            node_id="n1", execution_unit_id="u1", dependencies=[],
            dependents=[], ready=True, blocked=True, metadata={},
        )
        graph = _graph(
            nodes=[bad], edges=[], root_nodes=["n1"], leaf_nodes=["n1"],
            ready_nodes=["n1"], blocked_nodes=["n1"],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(graph)

    def test_unknown_dependency_rejected(self):
        graph = _graph(
            nodes=[_node("node-1", deps=["ghost"], ready=False)],
            edges=[], root_nodes=[], leaf_nodes=["node-1"],
            ready_nodes=[], blocked_nodes=["node-1"],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(graph)

    def test_edge_unknown_node_rejected(self):
        graph = _graph(
            edges=[ExecutionEdge(source_node="node-1", target_node="ghost")]
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(graph)

    def test_self_edge_rejected(self):
        graph = _graph(
            edges=[ExecutionEdge(source_node="node-1", target_node="node-1")]
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(graph)

    def test_root_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(
                _graph(root_nodes=["node-2"])
            )

    def test_ready_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_dependency_graph(
                _graph(ready_nodes=["node-2"])
            )

    def test_builder_output_always_validates(self):
        cases = [
            (_CHAIN, [_lc("u1", "READY"), _lc("u2", "WAITING"),
                      _lc("u3", "WAITING")]),
            (_CHAIN, [_lc("u1", "COMPLETED"), _lc("u2", "READY"),
                      _lc("u3", "WAITING")]),
            ([], []),
        ]
        for units, lifecycles in cases:
            with self.subTest(units=len(units)):
                self.validator.validate_execution_dependency_graph(
                    _build(units, lifecycles)
                )


# =====================================================================
# PlanningExplanationBuilder.build_with_execution_dependency_graph
# =====================================================================
class BuildWithGraphTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_describes_structure(self):
        graph = _build(_CHAIN, [_lc("u1", "READY"), _lc("u2", "WAITING"),
                                _lc("u3", "WAITING")])
        text = self.builder.build_with_execution_dependency_graph(
            self.plan, graph
        )
        self.assertIn("mapped 3 tasks", text)
        self.assertIn("1 can start", text)

    def test_cycle_message(self):
        graph = _build([_unit(1, [2]), _unit(2, [1])],
                       [_lc("u1", "READY"), _lc("u2", "READY")])
        text = self.builder.build_with_execution_dependency_graph(
            self.plan, graph
        )
        self.assertIn("loop", text)

    def test_empty_graph_message(self):
        text = self.builder.build_with_execution_dependency_graph(
            self.plan, _build([], [])
        )
        self.assertIn("no task dependencies", text)

    def test_reuses_base_narration(self):
        graph = _build(_CHAIN, [_lc("u1", "READY"), _lc("u2", "WAITING"),
                                _lc("u3", "WAITING")])
        text = self.builder.build_with_execution_dependency_graph(
            self.plan, graph
        )
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_execution_dependency_graph
# =====================================================================
class PlanningEngineCreateGraphTests(unittest.TestCase):
    def setUp(self):
        self.queue = _queue(_CHAIN)
        self.lifecycles = [_lc("u1", "READY")]
        self.graph = _graph()
        self.validator = MagicMock()
        self.graph_builder = MagicMock(name="Builder")
        self.graph_builder.build_graph.return_value = self.graph
        self.engine = PlanningEngine(
            MagicMock(), self.validator, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), self.graph_builder,
        )

    def test_delegates_to_builder(self):
        self.engine.create_execution_dependency_graph(
            self.queue, self.lifecycles
        )
        self.graph_builder.build_graph.assert_called_once_with(
            self.queue, self.lifecycles
        )

    def test_validates_the_graph(self):
        self.engine.create_execution_dependency_graph(
            self.queue, self.lifecycles
        )
        self.validator.validate_execution_dependency_graph.assert_called_once_with(
            self.graph
        )

    def test_returns_validated_graph_unchanged(self):
        self.assertIs(
            self.engine.create_execution_dependency_graph(
                self.queue, self.lifecycles
            ),
            self.graph,
        )

    def test_builder_exception_propagates(self):
        self.graph_builder.build_graph.side_effect = RuntimeError("x")
        with self.assertRaises(RuntimeError):
            self.engine.create_execution_dependency_graph(
                self.queue, self.lifecycles
            )

    def test_builder_stored_as_attribute(self):
        self.assertIs(self.engine.dependency_graph_builder, self.graph_builder)

    def test_engine_without_builder_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_execution_dependency_graph(self.queue, self.lifecycles)


class PlanningEngineGraphIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_graph(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        intent = self.engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        workflow = self.engine.create_execution_workflow(
            plan, analysis, preparation, decision, intent
        )
        queue = self.engine.create_execution_queue(workflow)
        lifecycles = self.engine.create_task_lifecycles(queue)
        graph = self.engine.create_execution_dependency_graph(queue, lifecycles)
        self.assertEqual(len(graph.nodes), len(plan.steps))
        self.assertFalse(graph.has_cycles)
        self.assertEqual(len(graph.root_nodes), 1)

    def test_engine_rejects_malformed_graph(self):
        bad = _graph(root_nodes=["node-2"])  # wrong roots
        graph_builder = MagicMock()
        graph_builder.build_graph.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            ExecutionCoordinator(),
            TaskLifecycleEngine(),
            ExecutionStateManager(),
            graph_builder,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_execution_dependency_graph(_queue(_CHAIN), [])


# =====================================================================
# Backward compatibility of the engine's construction shape
# =====================================================================
class EngineConstructionShapeTests(unittest.TestCase):
    def _base(self):
        return (
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
        )

    def _through_state_manager(self):
        return (
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            ExecutionCoordinator(),
            TaskLifecycleEngine(),
            ExecutionStateManager(),
        )

    def test_three_arg_engine_keeps_original_attributes(self):
        self.assertEqual(
            set(vars(PlanningEngine(*self._base()))),
            {"provider", "validator", "explanation_builder"},
        )

    def test_eleven_arg_engine_has_no_graph_builder(self):
        engine = PlanningEngine(*self._base(), *self._through_state_manager())
        self.assertNotIn("dependency_graph_builder", vars(engine))

    def test_twelve_arg_engine_adds_graph_builder(self):
        self.assertEqual(
            set(vars(_full_engine())),
            {
                "provider", "validator", "explanation_builder", "analyzer",
                "preparation_engine", "decision_engine", "intent_engine",
                "orchestrator", "coordinator", "lifecycle_engine",
                "state_manager", "dependency_graph_builder",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class GraphBuilderDependencyTests(unittest.TestCase):
    def test_get_builder_returns_builder(self):
        from app.core.dependencies import (
            get_execution_dependency_graph_builder,
        )

        self.assertIsInstance(
            get_execution_dependency_graph_builder(),
            ExecutionDependencyGraphBuilder,
        )

    def test_engine_injects_builder(self):
        from app.core.dependencies import get_planning_engine

        builder = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), builder,
        )
        self.assertIs(engine.dependency_graph_builder, builder)

    def test_engine_without_builder_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "dependency_graph_builder"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_coordinator,
            get_execution_dependency_graph_builder,
            get_execution_intent_engine,
            get_execution_orchestrator,
            get_execution_preparation_engine,
            get_execution_state_manager,
            get_plan_analyzer,
            get_plan_validator,
            get_planning_engine,
            get_planning_explanation_builder,
            get_planning_provider,
            get_task_lifecycle_engine,
        )

        engine = get_planning_engine(
            get_planning_provider(),
            get_plan_validator(),
            get_planning_explanation_builder(),
            get_plan_analyzer(),
            get_execution_preparation_engine(),
            get_decision_engine(),
            get_execution_intent_engine(),
            get_execution_orchestrator(),
            get_execution_coordinator(),
            get_task_lifecycle_engine(),
            get_execution_state_manager(),
            get_execution_dependency_graph_builder(),
        )
        plan = engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = engine.analyze(plan)
        preparation = engine.prepare(plan, analysis)
        decision = engine.decide(plan, analysis, preparation)
        intent = engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        workflow = engine.create_execution_workflow(
            plan, analysis, preparation, decision, intent
        )
        queue = engine.create_execution_queue(workflow)
        lifecycles = engine.create_task_lifecycles(queue)
        graph = engine.create_execution_dependency_graph(queue, lifecycles)
        self.assertIsInstance(graph, ExecutionDependencyGraph)
        self.assertTrue(
            engine.explanation_builder.build_with_execution_dependency_graph(
                plan, graph
            )
        )


# =====================================================================
# Regression: Sprint 13.1–13.9 behaviour unchanged
# =====================================================================
class Sprint131To139RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_execution_state_still_works(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        analysis = self.engine.analyze(plan)
        preparation = self.engine.prepare(plan, analysis)
        decision = self.engine.decide(plan, analysis, preparation)
        intent = self.engine.create_execution_intent(
            plan, analysis, preparation, decision
        )
        workflow = self.engine.create_execution_workflow(
            plan, analysis, preparation, decision, intent
        )
        queue = self.engine.create_execution_queue(workflow)
        lifecycles = self.engine.create_task_lifecycles(queue)
        state = self.engine.create_execution_state(lifecycles)
        self.assertEqual(state.total_tasks, len(plan.steps))

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
