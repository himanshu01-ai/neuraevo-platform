"""Unit tests for the Sprint 13.7 Execution Coordinator.

Covers the additive queue layer end to end without touching any network, SDK,
AI, tool execution, permission check, registry, runtime, memory, or database:

* the immutable :class:`ExecutionQueue` / :class:`ExecutionUnit` DTOs and the
  :class:`QueueStatus` / :class:`ExecutionUnitStatus` enums (defaults,
  immutability, JSON round-trip);
* the deterministic :class:`ExecutionCoordinator` (unit conversion, order/group/
  dependency preservation, status derivation, ready/blocked counts, ids,
  determinism, statelessness, purity);
* the extended :class:`PlanValidator` (``validate_execution_queue``);
* the extended :class:`PlanningExplanationBuilder` (``build_with_execution_queue``);
* the extended :class:`PlanningEngine` (``create_execution_queue`` +
  backward-compatible injection alongside the 13.2–13.6 collaborators);
* the composition-root wiring (``get_execution_coordinator`` + injection); and
* regression that Sprint 13.1–13.6 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_execution_coordinator
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
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnit,
    ExecutionUnitStatus,
    QueueStatus,
)
from app.services.planning.execution_workflow_models import (
    ExecutionWorkflow,
    WorkflowStep,
)
from app.services.planning.plan_analyzer import PlanAnalyzer


# =====================================================================
# Helpers
# =====================================================================
def _workflow(status="READY", mode="SEQUENTIAL", n=4, workflow_id="wf-test123"):
    steps = [
        WorkflowStep(
            step_number=i + 1,
            description=f"Step {i + 1}",
            group=i + 1,
            depends_on=[i] if i > 0 else [],
        )
        for i in range(n)
    ]
    return ExecutionWorkflow(
        workflow_id=workflow_id,
        workflow_status=status,
        ordered_steps=steps,
        estimated_total_steps=n,
        execution_mode=mode,
        resumable=status != "PLANNED",
        metadata={},
    )


def _create(workflow):
    return ExecutionCoordinator().create_queue(workflow)


def _unit(step_number=1, status="READY", group=1, unit_id=None, depends_on=None):
    return ExecutionUnit(
        unit_id=unit_id or f"u{step_number}",
        step_number=step_number,
        description=f"Step {step_number}",
        execution_group=group,
        status=status,
        dependencies=depends_on or [],
    )


def _queue(**overrides):
    units = overrides.pop(
        "execution_units",
        [_unit(1, "READY"), _unit(2, "BLOCKED", group=2, depends_on=[1])],
    )
    data = dict(
        queue_id="queue-wf-1",
        workflow_id="wf-1",
        status=QueueStatus.READY.value,
        execution_units=units,
        total_units=len(units),
        ready_units=sum(1 for u in units if u.status == "READY"),
        blocked_units=sum(1 for u in units if u.status == "BLOCKED"),
        metadata={},
    )
    data.update(overrides)
    return ExecutionQueue(**data)


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
    )


# =====================================================================
# DTOs / enums
# =====================================================================
class ExecutionQueueModelTests(unittest.TestCase):
    def test_defaults(self):
        queue = ExecutionQueue(
            queue_id="q1",
            workflow_id="wf1",
            status="READY",
            total_units=0,
            ready_units=0,
            blocked_units=0,
        )
        self.assertEqual(queue.execution_units, [])
        self.assertEqual(queue.metadata, {})

    def test_unit_defaults(self):
        unit = ExecutionUnit(
            unit_id="u1",
            step_number=1,
            description="A",
            execution_group=1,
            status="READY",
        )
        self.assertEqual(unit.dependencies, [])
        self.assertEqual(unit.metadata, {})

    def test_queue_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ExecutionQueue(queue_id="q1")  # others missing

    def test_is_immutable(self):
        with self.assertRaises(ValidationError):
            _queue().status = "BLOCKED"

    def test_unit_is_immutable(self):
        with self.assertRaises(ValidationError):
            _unit().status = "BLOCKED"

    def test_json_round_trip(self):
        queue = _queue()
        restored = ExecutionQueue.model_validate_json(queue.model_dump_json())
        self.assertEqual(restored, queue)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in QueueStatus}, {"READY", "WAITING", "BLOCKED"}
        )
        self.assertEqual(
            {s.value for s in ExecutionUnitStatus},
            {"READY", "WAITING", "BLOCKED"},
        )


# =====================================================================
# ExecutionCoordinator — conversion & preservation
# =====================================================================
class QueueConversionTests(unittest.TestCase):
    def test_one_unit_per_workflow_step(self):
        queue = _create(_workflow(n=4))
        self.assertEqual(queue.total_units, 4)
        self.assertEqual(len(queue.execution_units), 4)

    def test_preserves_order(self):
        queue = _create(_workflow(n=3))
        self.assertEqual(
            [u.step_number for u in queue.execution_units], [1, 2, 3]
        )

    def test_preserves_groups(self):
        workflow = _workflow(n=3)
        queue = _create(workflow)
        self.assertEqual(
            [u.execution_group for u in queue.execution_units],
            [s.group for s in workflow.ordered_steps],
        )

    def test_preserves_dependencies(self):
        queue = _create(_workflow(n=3))
        self.assertEqual(queue.execution_units[0].dependencies, [])
        self.assertEqual(queue.execution_units[1].dependencies, [1])

    def test_links_back_to_workflow(self):
        queue = _create(_workflow(workflow_id="wf-xyz"))
        self.assertEqual(queue.workflow_id, "wf-xyz")
        self.assertTrue(queue.queue_id.startswith("queue-"))
        self.assertIn("wf-xyz", queue.queue_id)

    def test_unit_ids_unique_and_deterministic(self):
        queue = _create(_workflow(n=3, workflow_id="wf-abc"))
        ids = [u.unit_id for u in queue.execution_units]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(ids[0], "wf-abc-u1")


# =====================================================================
# ExecutionCoordinator — status derivation & counts
# =====================================================================
class QueueStatusTests(unittest.TestCase):
    def test_ready_workflow_first_unit_ready_rest_blocked(self):
        queue = _create(_workflow(status="READY", n=4))
        self.assertEqual(queue.status, "READY")
        self.assertEqual(queue.ready_units, 1)
        self.assertEqual(queue.blocked_units, 3)
        self.assertEqual(queue.execution_units[0].status, "READY")
        self.assertEqual(queue.execution_units[1].status, "BLOCKED")

    def test_waiting_workflow_all_units_waiting(self):
        queue = _create(_workflow(status="WAITING", n=3))
        self.assertEqual(queue.status, "WAITING")
        self.assertEqual(queue.ready_units, 0)
        self.assertEqual(queue.blocked_units, 0)
        self.assertTrue(all(u.status == "WAITING" for u in queue.execution_units))

    def test_blocked_workflow_all_units_blocked(self):
        queue = _create(_workflow(status="BLOCKED", n=3))
        self.assertEqual(queue.status, "BLOCKED")
        self.assertEqual(queue.blocked_units, 3)

    def test_planned_workflow_maps_to_blocked_queue(self):
        queue = _create(_workflow(status="PLANNED", n=3))
        self.assertEqual(queue.status, "BLOCKED")
        self.assertEqual(queue.blocked_units, 3)

    def test_ready_workflow_all_independent_units_ready(self):
        steps = [
            WorkflowStep(step_number=i + 1, description=f"S{i+1}", group=1)
            for i in range(3)
        ]
        workflow = ExecutionWorkflow(
            workflow_id="wf-par",
            workflow_status="READY",
            ordered_steps=steps,
            estimated_total_steps=3,
            execution_mode="PARALLEL",
            resumable=True,
            metadata={},
        )
        queue = _create(workflow)
        self.assertEqual(queue.ready_units, 3)
        self.assertEqual(queue.blocked_units, 0)


# =====================================================================
# ExecutionCoordinator — quality
# =====================================================================
class CoordinatorQualityTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = ExecutionCoordinator()

    def test_metadata_records_context(self):
        queue = self.coordinator.create_queue(
            _workflow(status="WAITING", mode="HYBRID")
        )
        self.assertEqual(queue.metadata["workflow_status"], "WAITING")
        self.assertEqual(queue.metadata["execution_mode"], "HYBRID")

    def test_empty_workflow_yields_empty_queue(self):
        workflow = ExecutionWorkflow(
            workflow_id="wf-empty",
            workflow_status="READY",
            ordered_steps=[],
            estimated_total_steps=0,
            execution_mode="SEQUENTIAL",
            resumable=True,
            metadata={},
        )
        queue = self.coordinator.create_queue(workflow)
        self.assertEqual(queue.total_units, 0)
        self.assertEqual(queue.ready_units, 0)
        self.assertEqual(queue.blocked_units, 0)

    def test_deterministic(self):
        workflow = _workflow(status="READY", n=5)
        self.assertEqual(
            self.coordinator.create_queue(workflow),
            self.coordinator.create_queue(workflow),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.coordinator), {})

    def test_does_not_mutate_workflow(self):
        workflow = _workflow(n=4)
        before = workflow.model_dump()
        self.coordinator.create_queue(workflow)
        self.assertEqual(workflow.model_dump(), before)

    def test_produces_execution_queue(self):
        self.assertIsInstance(
            self.coordinator.create_queue(_workflow()), ExecutionQueue
        )


# =====================================================================
# PlanValidator.validate_execution_queue
# =====================================================================
class ValidateQueueTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_queue_passes(self):
        self.validator.validate_execution_queue(_queue())  # no raise

    def test_empty_queue_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(_queue(queue_id="  "))

    def test_empty_workflow_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(_queue(workflow_id=""))

    def test_invalid_queue_status_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(_queue(status="RUNNING"))

    def test_invalid_unit_status_rejected(self):
        queue = _queue(
            execution_units=[_unit(1, "RUNNING")],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(queue)

    def test_negative_counts_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(
                _queue(execution_units=[], ready_units=-1)
            )

    def test_count_mismatch_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(_queue(total_units=99))

    def test_duplicate_unit_ids_rejected(self):
        queue = _queue(
            execution_units=[
                _unit(1, "READY", unit_id="dup"),
                _unit(2, "READY", unit_id="dup"),
            ],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(queue)

    def test_duplicate_step_numbers_rejected(self):
        queue = _queue(
            execution_units=[
                _unit(1, "READY", unit_id="a"),
                _unit(1, "READY", unit_id="b"),
            ],
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(queue)

    def test_non_positive_group_rejected(self):
        queue = _queue(execution_units=[_unit(1, "READY", group=0)])
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(queue)

    def test_ready_count_mismatch_rejected(self):
        queue = _queue(
            execution_units=[_unit(1, "READY")], ready_units=5
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(queue)

    def test_blocked_count_mismatch_rejected(self):
        queue = _queue(
            execution_units=[_unit(1, "BLOCKED")], blocked_units=0
        )
        with self.assertRaises(PlanValidationError):
            self.validator.validate_execution_queue(queue)

    def test_coordinator_output_always_validates(self):
        for status in ("READY", "WAITING", "BLOCKED", "PLANNED"):
            with self.subTest(status=status):
                self.validator.validate_execution_queue(
                    _create(_workflow(status=status, n=5))
                )


# =====================================================================
# PlanningExplanationBuilder.build_with_execution_queue
# =====================================================================
class BuildWithQueueTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_ready_message(self):
        text = self.builder.build_with_execution_queue(
            self.plan, _queue(status="READY")
        )
        self.assertIn("ready to begin", text)

    def test_waiting_message(self):
        text = self.builder.build_with_execution_queue(
            self.plan,
            _queue(
                status="WAITING",
                execution_units=[_unit(1, "WAITING")],
            ),
        )
        self.assertIn("waiting for you", text)

    def test_mentions_counts(self):
        text = self.builder.build_with_execution_queue(self.plan, _queue())
        self.assertIn("items", text)
        self.assertIn("ready", text)
        self.assertIn("blocked", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_execution_queue(self.plan, _queue())
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_execution_queue
# =====================================================================
class PlanningEngineCreateQueueTests(unittest.TestCase):
    def setUp(self):
        self.workflow = _workflow()
        self.queue = _queue()
        self.validator = MagicMock()
        self.coordinator = MagicMock(name="ExecutionCoordinator")
        self.coordinator.create_queue.return_value = self.queue
        self.engine = PlanningEngine(
            MagicMock(),
            self.validator,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            self.coordinator,
        )

    def test_delegates_to_coordinator_with_workflow(self):
        self.engine.create_execution_queue(self.workflow)
        self.coordinator.create_queue.assert_called_once_with(self.workflow)

    def test_validates_the_queue(self):
        self.engine.create_execution_queue(self.workflow)
        self.validator.validate_execution_queue.assert_called_once_with(
            self.queue
        )

    def test_returns_validated_queue_unchanged(self):
        self.assertIs(
            self.engine.create_execution_queue(self.workflow), self.queue
        )

    def test_coordinator_exception_propagates(self):
        self.coordinator.create_queue.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.engine.create_execution_queue(self.workflow)

    def test_coordinator_stored_as_attribute(self):
        self.assertIs(self.engine.coordinator, self.coordinator)

    def test_engine_without_coordinator_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_execution_queue(self.workflow)


class PlanningEngineQueueIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_queue(self):
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
        self.assertEqual(queue.total_units, len(plan.steps))
        self.assertEqual(queue.status, "WAITING")

    def test_engine_rejects_malformed_queue(self):
        bad = _queue(status="RUNNING")
        coordinator = MagicMock()
        coordinator.create_queue.return_value = bad
        engine = PlanningEngine(
            HeuristicPlanningProvider(),
            PlanValidator(),
            PlanningExplanationBuilder(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            coordinator,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_execution_queue(_workflow())


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

    def test_three_arg_engine_keeps_original_attributes(self):
        self.assertEqual(
            set(vars(PlanningEngine(*self._base()))),
            {"provider", "validator", "explanation_builder"},
        )

    def test_eight_arg_engine_has_no_coordinator(self):
        engine = PlanningEngine(
            *self._base(),
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
        )
        self.assertNotIn("coordinator", vars(engine))

    def test_nine_arg_engine_adds_coordinator(self):
        self.assertEqual(
            set(vars(_full_engine())),
            {
                "provider",
                "validator",
                "explanation_builder",
                "analyzer",
                "preparation_engine",
                "decision_engine",
                "intent_engine",
                "orchestrator",
                "coordinator",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ExecutionCoordinatorDependencyTests(unittest.TestCase):
    def test_get_execution_coordinator_returns_coordinator(self):
        from app.core.dependencies import get_execution_coordinator

        self.assertIsInstance(
            get_execution_coordinator(), ExecutionCoordinator
        )

    def test_engine_injects_coordinator(self):
        from app.core.dependencies import get_planning_engine

        coordinator = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), coordinator,
        )
        self.assertIs(engine.coordinator, coordinator)

    def test_engine_without_coordinator_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "coordinator"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_coordinator,
            get_execution_intent_engine,
            get_execution_orchestrator,
            get_execution_preparation_engine,
            get_plan_analyzer,
            get_plan_validator,
            get_planning_engine,
            get_planning_explanation_builder,
            get_planning_provider,
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
        self.assertIsInstance(queue, ExecutionQueue)
        self.assertIn(queue.status, {s.value for s in QueueStatus})
        self.assertTrue(
            engine.explanation_builder.build_with_execution_queue(plan, queue)
        )


# =====================================================================
# Regression: Sprint 13.1–13.6 behaviour unchanged
# =====================================================================
class Sprint131To136RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_workflow_still_works(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="business strategy grow revenue")
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
        self.assertEqual(workflow.execution_mode, "PARALLEL")

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
