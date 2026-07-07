"""Unit tests for the Sprint 13.14 Human Approval Manager.

Covers the additive approval-governance layer end to end without touching any
network, SDK, AI, tool execution, permission check, registry, runtime, memory, or
database:

* the immutable :class:`ApprovalPlan` / :class:`ApprovalCheckpoint` DTOs and the
  :class:`ApprovalStrategy` enum (defaults, immutability, JSON round-trip);
* the deterministic :class:`HumanApprovalManager` (strategy selection, checkpoint
  creation, pending/approved/blocked identification, empty execution,
  determinism, statelessness, input non-mutation);
* the extended :class:`PlanValidator` (``validate_approval_plan``);
* the extended :class:`PlanningExplanationBuilder` (``build_with_approval_plan``);
* the extended :class:`PlanningEngine` (``create_approval_plan`` +
  backward-compatible injection alongside the 13.2–13.13 collaborators);
* the composition-root wiring (``get_human_approval_manager`` + injection); and
* regression that Sprint 13.1–13.13 behaviour is unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_human_approval_manager
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
from app.services.planning.approval_models import (
    ApprovalCheckpoint,
    ApprovalPlan,
    ApprovalStrategy,
)
from app.services.planning.decision_engine import DecisionEngine
from app.services.planning.execution_coordinator import ExecutionCoordinator
from app.services.planning.execution_dependency_graph import (
    ExecutionDependencyGraphBuilder,
)
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_intent_models import ExecutionIntent
from app.services.planning.execution_monitor import ExecutionMonitor
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_schedule_models import (
    ExecutionSchedule,
    ScheduledNode,
)
from app.services.planning.execution_scheduler import ExecutionScheduler
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.human_approval_manager import HumanApprovalManager
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.recovery_manager import RecoveryManager
from app.services.planning.recovery_models import RecoveryPlan
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine


# =====================================================================
# Helpers
# =====================================================================
def _intent(intent_type="EXECUTE_NOW"):
    return ExecutionIntent(
        intent=intent_type,
        should_execute=intent_type == "EXECUTE_NOW",
        requires_user_action=intent_type == "WAIT_FOR_USER",
        recommended_next_step="Proceed with the next step.",
        execution_priority=1,
        defer_reason="Deferred." if intent_type == "DEFER" else "",
    )


def _sched_node(node_id, priority):
    return ScheduledNode(
        node_id=node_id,
        execution_unit_id=f"unit-{node_id}",
        priority=priority,
        scheduled=True,
        reason="Ready and selected for execution.",
        metadata={},
    )


def _schedule(scheduled=("n1",), deferred=(), blocked=(), execution_id="exec-x"):
    nodes = [_sched_node(n, i + 1) for i, n in enumerate(scheduled)]
    return ExecutionSchedule(
        schedule_id=f"schedule-{execution_id}",
        execution_id=execution_id,
        scheduled_nodes=nodes,
        deferred_nodes=list(deferred),
        blocked_nodes=list(blocked),
        execution_order=[n.node_id for n in nodes],
        scheduling_strategy="SEQUENTIAL",
        metadata={},
    )


def _recovery(strategy="NO_ACTION", execution_id="exec-x"):
    if strategy == "NO_ACTION":
        affected, recoverable, unrecoverable = [], [], []
    elif strategy in ("RETRY", "RESUME"):
        affected, recoverable, unrecoverable = ["n2"], ["n2"], []
    else:  # REPLAN, ABORT
        affected, recoverable, unrecoverable = ["n2"], [], ["n2"]
    return RecoveryPlan(
        recovery_id=f"recovery-{execution_id}",
        execution_id=execution_id,
        recovery_strategy=strategy,
        affected_nodes=affected,
        recoverable_nodes=recoverable,
        unrecoverable_nodes=unrecoverable,
        requires_user_intervention=strategy in ("REPLAN", "ABORT"),
        recovery_reason="reason",
        metadata={},
    )


def _create(intent=None, schedule=None, recovery=None):
    return HumanApprovalManager().create_approval_plan(
        intent if intent is not None else _intent(),
        schedule if schedule is not None else _schedule(),
        recovery if recovery is not None else _recovery(),
    )


def _checkpoint(
    checkpoint_id="checkpoint-unit-n1", unit_id="unit-n1", required=True
):
    return ApprovalCheckpoint(
        checkpoint_id=checkpoint_id,
        execution_unit_id=unit_id,
        reason="Approval required before this step runs.",
        required=required,
        metadata={},
    )


def _approval(**overrides):
    checkpoints = overrides.pop("approval_checkpoints", [_checkpoint()])
    data = dict(
        approval_id="approval-exec-x",
        execution_id="exec-x",
        approval_strategy="BEFORE_EXECUTION",
        approval_checkpoints=checkpoints,
        pending_approvals=[cp.checkpoint_id for cp in checkpoints],
        approved_nodes=[],
        blocked_nodes=["n1"],
        requires_approval=True,
        approval_reason="reason",
        metadata={},
    )
    data.update(overrides)
    return ApprovalPlan(**data)


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
        ExecutionScheduler(),
        ExecutionMonitor(),
        RecoveryManager(),
        HumanApprovalManager(),
    )


# =====================================================================
# DTOs
# =====================================================================
class ApprovalModelTests(unittest.TestCase):
    def test_plan_defaults(self):
        plan = ApprovalPlan(
            approval_id="a1",
            execution_id="e1",
            approval_strategy="NO_APPROVAL",
            requires_approval=False,
            approval_reason="ok",
        )
        self.assertEqual(plan.approval_checkpoints, [])
        self.assertEqual(plan.pending_approvals, [])
        self.assertEqual(plan.approved_nodes, [])
        self.assertEqual(plan.blocked_nodes, [])
        self.assertEqual(plan.metadata, {})

    def test_checkpoint_defaults(self):
        checkpoint = ApprovalCheckpoint(
            checkpoint_id="c1",
            execution_unit_id="u1",
            reason="r",
            required=True,
        )
        self.assertEqual(checkpoint.metadata, {})

    def test_requires_core_fields(self):
        with self.assertRaises(ValidationError):
            ApprovalPlan(approval_id="a1")  # rest missing

    def test_immutable(self):
        with self.assertRaises(ValidationError):
            _approval().approval_strategy = "NO_APPROVAL"
        with self.assertRaises(ValidationError):
            _checkpoint().required = False

    def test_json_round_trip(self):
        plan = _create(
            _intent("EXECUTE_NOW"),
            _schedule(("n1", "n2")),
            _recovery("RETRY"),
        )
        restored = ApprovalPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)

    def test_enum_values(self):
        self.assertEqual(
            {s.value for s in ApprovalStrategy},
            {
                "NO_APPROVAL",
                "BEFORE_EXECUTION",
                "BEFORE_RECOVERY",
                "MANUAL_REVIEW",
            },
        )


# =====================================================================
# HumanApprovalManager — strategy selection (the deterministic rules)
# =====================================================================
class ApprovalStrategyTests(unittest.TestCase):
    def test_no_action_execute_now_is_no_approval(self):
        plan = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("NO_ACTION"))
        self.assertEqual(plan.approval_strategy, "NO_APPROVAL")

    def test_retry_is_before_recovery(self):
        plan = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("RETRY"))
        self.assertEqual(plan.approval_strategy, "BEFORE_RECOVERY")

    def test_resume_is_before_recovery(self):
        plan = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("RESUME"))
        self.assertEqual(plan.approval_strategy, "BEFORE_RECOVERY")

    def test_replan_is_manual_review(self):
        plan = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("REPLAN"))
        self.assertEqual(plan.approval_strategy, "MANUAL_REVIEW")

    def test_abort_is_manual_review(self):
        plan = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("ABORT"))
        self.assertEqual(plan.approval_strategy, "MANUAL_REVIEW")

    def test_wait_for_user_is_before_execution(self):
        plan = _create(
            _intent("WAIT_FOR_USER"), _schedule(), _recovery("NO_ACTION")
        )
        self.assertEqual(plan.approval_strategy, "BEFORE_EXECUTION")

    def test_recovery_takes_precedence_over_intent(self):
        plan = _create(
            _intent("WAIT_FOR_USER"), _schedule(), _recovery("RETRY")
        )
        self.assertEqual(plan.approval_strategy, "BEFORE_RECOVERY")

    def test_defer_intent_is_no_approval(self):
        plan = _create(_intent("DEFER"), _schedule(), _recovery("NO_ACTION"))
        self.assertEqual(plan.approval_strategy, "NO_APPROVAL")

    def test_empty_execution_is_no_approval(self):
        plan = _create(
            _intent("WAIT_FOR_USER"),
            _schedule(scheduled=(), deferred=(), blocked=()),
            _recovery("REPLAN"),
        )
        self.assertEqual(plan.approval_strategy, "NO_APPROVAL")


# =====================================================================
# HumanApprovalManager — requires_approval flag
# =====================================================================
class ApprovalRequiresTests(unittest.TestCase):
    def test_no_approval_requires_nothing(self):
        self.assertFalse(
            _create(_intent("EXECUTE_NOW"), _schedule(), _recovery()).
            requires_approval
        )

    def test_before_execution_requires_approval(self):
        self.assertTrue(
            _create(_intent("WAIT_FOR_USER"), _schedule(), _recovery()).
            requires_approval
        )

    def test_before_recovery_requires_approval(self):
        self.assertTrue(
            _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("RETRY")).
            requires_approval
        )

    def test_manual_review_requires_approval(self):
        self.assertTrue(
            _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("ABORT")).
            requires_approval
        )


# =====================================================================
# HumanApprovalManager — checkpoints & node groups
# =====================================================================
class ApprovalNodeTests(unittest.TestCase):
    def test_no_approval_clears_nodes(self):
        plan = _create(
            _intent("EXECUTE_NOW"), _schedule(("n1", "n2")), _recovery()
        )
        self.assertEqual(plan.approved_nodes, ["n1", "n2"])
        self.assertEqual(plan.blocked_nodes, [])
        self.assertEqual(plan.approval_checkpoints, [])
        self.assertEqual(plan.pending_approvals, [])

    def test_gated_creates_checkpoints(self):
        plan = _create(
            _intent("WAIT_FOR_USER"), _schedule(("n1", "n2")), _recovery()
        )
        self.assertEqual(len(plan.approval_checkpoints), 2)
        self.assertTrue(all(cp.required for cp in plan.approval_checkpoints))
        self.assertEqual(plan.blocked_nodes, ["n1", "n2"])
        self.assertEqual(plan.approved_nodes, [])

    def test_pending_matches_checkpoints(self):
        plan = _create(
            _intent("WAIT_FOR_USER"), _schedule(("n1", "n2")), _recovery()
        )
        self.assertEqual(
            plan.pending_approvals,
            [cp.checkpoint_id for cp in plan.approval_checkpoints],
        )

    def test_checkpoint_links_execution_unit(self):
        plan = _create(_intent("WAIT_FOR_USER"), _schedule(("n1",)), _recovery())
        self.assertEqual(
            plan.approval_checkpoints[0].execution_unit_id, "unit-n1"
        )

    def test_manual_review_without_scheduled_units(self):
        plan = _create(
            _intent("EXECUTE_NOW"),
            _schedule(scheduled=(), blocked=("n2",)),
            _recovery("REPLAN"),
        )
        self.assertEqual(plan.approval_strategy, "MANUAL_REVIEW")
        self.assertTrue(plan.requires_approval)
        self.assertEqual(plan.approval_checkpoints, [])
        self.assertEqual(plan.blocked_nodes, [])

    def test_links_execution_and_approval_id(self):
        plan = _create(schedule=_schedule(execution_id="exec-42"))
        self.assertEqual(plan.execution_id, "exec-42")
        self.assertIn("exec-42", plan.approval_id)

    def test_reason_is_populated(self):
        self.assertTrue(_create().approval_reason.strip())


# =====================================================================
# HumanApprovalManager — quality
# =====================================================================
class ApprovalQualityTests(unittest.TestCase):
    def setUp(self):
        self.manager = HumanApprovalManager()

    def test_deterministic(self):
        intent = _intent("WAIT_FOR_USER")
        schedule = _schedule(("n1", "n2"))
        recovery = _recovery("RETRY")
        self.assertEqual(
            self.manager.create_approval_plan(intent, schedule, recovery),
            self.manager.create_approval_plan(intent, schedule, recovery),
        )

    def test_stateless(self):
        self.assertEqual(vars(self.manager), {})

    def test_does_not_mutate_inputs(self):
        intent = _intent("WAIT_FOR_USER")
        schedule = _schedule(("n1", "n2"))
        recovery = _recovery("RETRY")
        before = (
            intent.model_dump(),
            schedule.model_dump(),
            recovery.model_dump(),
        )
        self.manager.create_approval_plan(intent, schedule, recovery)
        self.assertEqual(
            (
                intent.model_dump(),
                schedule.model_dump(),
                recovery.model_dump(),
            ),
            before,
        )

    def test_produces_approval_plan(self):
        self.assertIsInstance(_create(), ApprovalPlan)


# =====================================================================
# PlanValidator.validate_approval_plan
# =====================================================================
class ValidateApprovalTests(unittest.TestCase):
    def setUp(self):
        self.validator = PlanValidator()

    def test_valid_passes(self):
        self.validator.validate_approval_plan(_approval())

    def test_valid_no_approval_passes(self):
        self.validator.validate_approval_plan(
            _approval(
                approval_strategy="NO_APPROVAL",
                approval_checkpoints=[],
                approved_nodes=["n1"],
                blocked_nodes=[],
                requires_approval=False,
            )
        )

    def test_empty_approval_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(_approval(approval_id=" "))

    def test_empty_execution_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(_approval(execution_id=""))

    def test_invalid_strategy_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(approval_strategy="RUBBER_STAMP")
            )

    def test_empty_reason_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(_approval(approval_reason=" "))

    def test_empty_checkpoint_id_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(
                    approval_checkpoints=[_checkpoint(checkpoint_id=" ")],
                    pending_approvals=[],
                )
            )

    def test_empty_checkpoint_unit_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(
                    approval_checkpoints=[_checkpoint(unit_id="")],
                    pending_approvals=[],
                )
            )

    def test_duplicate_checkpoint_ids_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(
                    approval_checkpoints=[
                        _checkpoint(),
                        _checkpoint(unit_id="unit-n2"),
                    ],
                    pending_approvals=[],
                )
            )

    def test_empty_pending_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(pending_approvals=["  "])
            )

    def test_duplicate_pending_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(
                    pending_approvals=[
                        "checkpoint-unit-n1",
                        "checkpoint-unit-n1",
                    ]
                )
            )

    def test_pending_unknown_checkpoint_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(pending_approvals=["nope"])
            )

    def test_empty_blocked_node_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(blocked_nodes=["n1", " "])
            )

    def test_approved_blocked_overlap_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(approved_nodes=["n1"], blocked_nodes=["n1"])
            )

    def test_requires_approval_inconsistent_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(requires_approval=False)  # BEFORE_EXECUTION
            )

    def test_no_approval_with_checkpoints_rejected(self):
        with self.assertRaises(PlanValidationError):
            self.validator.validate_approval_plan(
                _approval(
                    approval_strategy="NO_APPROVAL",
                    requires_approval=False,
                    approved_nodes=["n1"],
                    blocked_nodes=[],
                    pending_approvals=[],
                )  # keeps the default checkpoint -> rejected
            )

    def test_manager_output_always_validates(self):
        cases = (
            (_intent("EXECUTE_NOW"), _schedule(), _recovery("NO_ACTION")),
            (_intent("WAIT_FOR_USER"), _schedule(), _recovery("NO_ACTION")),
            (_intent("EXECUTE_NOW"), _schedule(("n1", "n2")), _recovery("RETRY")),
            (_intent("EXECUTE_NOW"), _schedule(), _recovery("RESUME")),
            (
                _intent("EXECUTE_NOW"),
                _schedule(scheduled=(), blocked=("n2",)),
                _recovery("REPLAN"),
            ),
            (_intent("EXECUTE_NOW"), _schedule(), _recovery("ABORT")),
            (
                _intent("WAIT_FOR_USER"),
                _schedule(scheduled=(), deferred=(), blocked=()),
                _recovery("NO_ACTION"),
            ),
        )
        for intent, schedule, recovery in cases:
            with self.subTest(recovery=recovery.recovery_strategy):
                self.validator.validate_approval_plan(
                    HumanApprovalManager().create_approval_plan(
                        intent, schedule, recovery
                    )
                )


# =====================================================================
# PlanningExplanationBuilder.build_with_approval_plan
# =====================================================================
class BuildWithApprovalTests(unittest.TestCase):
    def setUp(self):
        self.builder = PlanningExplanationBuilder()
        self.plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )

    def test_describes_no_approval(self):
        approval = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery())
        text = self.builder.build_with_approval_plan(self.plan, approval)
        self.assertIn("go ahead", text.lower())

    def test_describes_before_execution(self):
        approval = _create(_intent("WAIT_FOR_USER"), _schedule(), _recovery())
        text = self.builder.build_with_approval_plan(self.plan, approval)
        self.assertIn("before i start", text.lower())

    def test_describes_before_recovery(self):
        approval = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("RETRY"))
        text = self.builder.build_with_approval_plan(self.plan, approval)
        self.assertIn("recover", text.lower())

    def test_describes_manual_review(self):
        approval = _create(_intent("EXECUTE_NOW"), _schedule(), _recovery("ABORT"))
        text = self.builder.build_with_approval_plan(self.plan, approval)
        self.assertIn("manual review", text.lower())

    def test_mentions_checkpoints(self):
        approval = _create(
            _intent("WAIT_FOR_USER"), _schedule(("n1", "n2")), _recovery()
        )
        text = self.builder.build_with_approval_plan(self.plan, approval)
        self.assertIn("2 checkpoint(s)", text)

    def test_reuses_base_narration(self):
        text = self.builder.build_with_approval_plan(self.plan, _create())
        self.assertIn("I will", text)


# =====================================================================
# PlanningEngine.create_approval_plan
# =====================================================================
class PlanningEngineCreateApprovalTests(unittest.TestCase):
    def setUp(self):
        self.intent = _intent()
        self.schedule = _schedule()
        self.recovery = _recovery()
        self.approval = _approval()
        self.validator = MagicMock()
        self.manager = MagicMock(name="HumanApprovalManager")
        self.manager.create_approval_plan.return_value = self.approval
        self.engine = PlanningEngine(
            MagicMock(), self.validator, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            self.manager,
        )

    def test_delegates_to_manager(self):
        self.engine.create_approval_plan(
            self.intent, self.schedule, self.recovery
        )
        self.manager.create_approval_plan.assert_called_once_with(
            self.intent, self.schedule, self.recovery
        )

    def test_validates_the_plan(self):
        self.engine.create_approval_plan(
            self.intent, self.schedule, self.recovery
        )
        self.validator.validate_approval_plan.assert_called_once_with(
            self.approval
        )

    def test_returns_validated_plan_unchanged(self):
        self.assertIs(
            self.engine.create_approval_plan(
                self.intent, self.schedule, self.recovery
            ),
            self.approval,
        )

    def test_manager_exception_propagates(self):
        self.manager.create_approval_plan.side_effect = RuntimeError("x")
        with self.assertRaises(RuntimeError):
            self.engine.create_approval_plan(
                self.intent, self.schedule, self.recovery
            )

    def test_manager_stored_as_attribute(self):
        self.assertIs(self.engine.approval_manager, self.manager)

    def test_engine_without_manager_raises(self):
        engine = PlanningEngine(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(RuntimeError):
            engine.create_approval_plan(
                self.intent, self.schedule, self.recovery
            )


class PlanningEngineApprovalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_full_pipeline_produces_valid_approval_plan(self):
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
        graph = self.engine.create_execution_dependency_graph(queue, lifecycles)
        schedule = self.engine.create_execution_schedule(graph, state)
        report = self.engine.create_execution_monitoring_report(schedule, state)
        recovery = self.engine.create_recovery_plan(report, state, graph)
        approval = self.engine.create_approval_plan(intent, schedule, recovery)
        self.assertEqual(approval.execution_id, schedule.execution_id)
        self.assertIn(
            approval.approval_strategy, {s.value for s in ApprovalStrategy}
        )

    def test_engine_rejects_malformed_approval_plan(self):
        bad = _approval(approval_strategy="RUBBER_STAMP")
        manager = MagicMock()
        manager.create_approval_plan.return_value = bad
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
            ExecutionDependencyGraphBuilder(),
            ExecutionScheduler(),
            ExecutionMonitor(),
            RecoveryManager(),
            manager,
        )
        with self.assertRaises(PlanValidationError):
            engine.create_approval_plan(_intent(), _schedule(), _recovery())


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

    def _through_recovery(self):
        return (
            PlanAnalyzer(),
            ExecutionPreparationEngine(),
            DecisionEngine(),
            ExecutionIntentEngine(),
            ExecutionOrchestrator(),
            ExecutionCoordinator(),
            TaskLifecycleEngine(),
            ExecutionStateManager(),
            ExecutionDependencyGraphBuilder(),
            ExecutionScheduler(),
            ExecutionMonitor(),
            RecoveryManager(),
        )

    def test_three_arg_engine_keeps_original_attributes(self):
        self.assertEqual(
            set(vars(PlanningEngine(*self._base()))),
            {"provider", "validator", "explanation_builder"},
        )

    def test_fifteen_arg_engine_has_no_approval_manager(self):
        engine = PlanningEngine(*self._base(), *self._through_recovery())
        self.assertNotIn("approval_manager", vars(engine))

    def test_sixteen_arg_engine_adds_approval_manager(self):
        self.assertEqual(
            set(vars(_full_engine())),
            {
                "provider", "validator", "explanation_builder", "analyzer",
                "preparation_engine", "decision_engine", "intent_engine",
                "orchestrator", "coordinator", "lifecycle_engine",
                "state_manager", "dependency_graph_builder", "scheduler",
                "monitor", "recovery_manager", "approval_manager",
            },
        )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class ApprovalDependencyTests(unittest.TestCase):
    def test_get_manager_returns_manager(self):
        from app.core.dependencies import get_human_approval_manager

        self.assertIsInstance(
            get_human_approval_manager(), HumanApprovalManager
        )

    def test_engine_injects_manager(self):
        from app.core.dependencies import get_planning_engine

        manager = MagicMock()
        engine = get_planning_engine(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            manager,
        )
        self.assertIs(engine.approval_manager, manager)

    def test_engine_without_manager_backward_compatible(self):
        from app.core.dependencies import get_planning_engine

        engine = get_planning_engine(MagicMock(), MagicMock(), MagicMock())
        self.assertFalse(hasattr(engine, "approval_manager"))

    def test_composition_root_end_to_end(self):
        from app.core.dependencies import (
            get_decision_engine,
            get_execution_coordinator,
            get_execution_dependency_graph_builder,
            get_execution_intent_engine,
            get_execution_monitor,
            get_execution_orchestrator,
            get_execution_preparation_engine,
            get_execution_scheduler,
            get_execution_state_manager,
            get_human_approval_manager,
            get_plan_analyzer,
            get_plan_validator,
            get_planning_engine,
            get_planning_explanation_builder,
            get_planning_provider,
            get_recovery_manager,
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
            get_execution_scheduler(),
            get_execution_monitor(),
            get_recovery_manager(),
            get_human_approval_manager(),
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
        state = engine.create_execution_state(lifecycles)
        graph = engine.create_execution_dependency_graph(queue, lifecycles)
        schedule = engine.create_execution_schedule(graph, state)
        report = engine.create_execution_monitoring_report(schedule, state)
        recovery = engine.create_recovery_plan(report, state, graph)
        approval = engine.create_approval_plan(intent, schedule, recovery)
        self.assertIsInstance(approval, ApprovalPlan)
        self.assertIn(
            approval.approval_strategy, {s.value for s in ApprovalStrategy}
        )
        self.assertTrue(
            engine.explanation_builder.build_with_approval_plan(plan, approval)
        )


# =====================================================================
# Regression: Sprint 13.1–13.13 behaviour unchanged
# =====================================================================
class Sprint131To1313RegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = _full_engine()

    def test_create_plan_unchanged(self):
        plan = self.engine.create_plan(
            PlanningRequest(user_request="Help me plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_recovery_plan_still_works(self):
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
        graph = self.engine.create_execution_dependency_graph(queue, lifecycles)
        schedule = self.engine.create_execution_schedule(graph, state)
        report = self.engine.create_execution_monitoring_report(schedule, state)
        recovery = self.engine.create_recovery_plan(report, state, graph)
        self.assertEqual(recovery.execution_id, state.execution_id)

    def test_base_explanation_still_works(self):
        plan = HeuristicPlanningProvider().create_plan(
            PlanningRequest(user_request="plan a trip")
        )
        self.assertIn("I will", PlanningExplanationBuilder().build(plan))


if __name__ == "__main__":
    unittest.main()
