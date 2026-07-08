"""Integration tests for the Sprint 14.15 Runtime Execution Orchestration pipeline.

Covers the single runtime coordinator —
:meth:`ExecutionRuntime.create_runtime_execution_orchestration` — which composes
every Sprint 14.1–14.14 runtime stage into one deterministic pipeline, plus the
composition-root ``get_runtime_execution_orchestrator`` seam. This is integration
only: no new runtime logic, DTO, manager, capability, network, SDK, or database.
It uses a deterministic in-test capability double (the real capability seam stays
unfulfilled). It verifies:

* the full runtime pipeline (all thirteen stages produced, chained);
* deterministic outputs (same inputs -> equal result);
* exact stage ordering;
* missing-collaborator propagation, provider-error propagation, and validation
  propagation;
* no mutation between stages (frozen outputs; re-run stability);
* orchestration equals manual composition;
* dependency injection (the wired coordinator; seam gating); and
* regression that Sprint 14.1 context creation and the Sprint 13 pipeline are
  unchanged.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_runtime_execution_orchestration_pipeline
"""

import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.core.dependencies import get_execution_orchestration_engine
from app.services.planning import PlanningRequest
from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnit,
)
from app.services.runtime.capability_dispatcher import CapabilityDispatcher
from app.services.runtime.capability_dispatcher_models import (
    CapabilityDispatchPlan,
)
from app.services.runtime.capability_executor import CapabilityExecutor
from app.services.runtime.capability_executor_models import (
    CapabilityExecutionSummary,
)
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionResult,
)
from app.services.runtime.execution_controller import ExecutionController
from app.services.runtime.execution_controller_models import (
    ExecutionControlState,
)
from app.services.runtime.execution_event_manager import ExecutionEventManager
from app.services.runtime.execution_event_models import ExecutionEventLog
from app.services.runtime.execution_lifecycle_manager import (
    ExecutionLifecycleManager,
)
from app.services.runtime.execution_lifecycle_models import (
    RuntimeExecutionLifecycle,
)
from app.services.runtime.execution_progress_models import ExecutionProgress
from app.services.runtime.execution_progress_runtime import (
    ExecutionProgressRuntime,
)
from app.services.runtime.execution_runtime import (
    ExecutionRuntime,
    RuntimeExecutionOrchestrationResult,
)
from app.services.runtime.execution_runtime_models import ExecutionRuntimeContext
from app.services.runtime.runtime_execution_monitor import (
    RuntimeExecutionMonitor,
)
from app.services.runtime.runtime_execution_monitor_models import (
    RuntimeExecutionHealth,
)
from app.services.runtime.runtime_execution_state_manager import (
    RuntimeExecutionStateManager,
)
from app.services.runtime.runtime_execution_state_models import (
    RuntimeExecutionState,
)
from app.services.runtime.runtime_pause_resume_manager import (
    RuntimePauseResumeManager,
)
from app.services.runtime.runtime_pause_resume_models import (
    RuntimePauseResumeState,
)
from app.services.runtime.runtime_recovery_coordinator import (
    RuntimeRecoveryCoordinator,
)
from app.services.runtime.runtime_recovery_models import RuntimeRecoveryState
from app.services.runtime.runtime_resource_coordinator import (
    RuntimeResourceCoordinator,
)
from app.services.runtime.runtime_resource_models import RuntimeResourceState
from app.services.runtime.task_dispatcher import TaskDispatcher
from app.services.runtime.task_dispatcher_models import DispatchPlan


# The runtime stage method names, in the exact pipeline order.
STAGES = [
    "create_context",
    "create_dispatch_plan",
    "create_capability_dispatch_plan",
    "execute",
    "create_progress",
    "create_control_state",
    "create_event_log",
    "create_lifecycle",
    "create_state",
    "create_health",
    "create_pause_resume_state",
    "create_recovery_state",
    "create_resource_state",
]

# The result NamedTuple fields, in pipeline order, with their expected types.
RESULT_TYPES = [
    ("context", ExecutionRuntimeContext),
    ("dispatch_plan", DispatchPlan),
    ("capability_dispatch_plan", CapabilityDispatchPlan),
    ("execution_summary", CapabilityExecutionSummary),
    ("progress", ExecutionProgress),
    ("control_state", ExecutionControlState),
    ("event_log", ExecutionEventLog),
    ("lifecycle", RuntimeExecutionLifecycle),
    ("state", RuntimeExecutionState),
    ("health", RuntimeExecutionHealth),
    ("pause_resume", RuntimePauseResumeState),
    ("recovery", RuntimeRecoveryState),
    ("resource", RuntimeResourceState),
]

FULL_ATTRS = {
    "task_dispatcher", "capability_dispatcher", "capability_executor",
    "progress_runtime", "controller", "event_manager", "lifecycle_manager",
    "state_manager", "monitor", "pause_resume_manager", "recovery_coordinator",
    "resource_coordinator",
}


# =====================================================================
# In-test capability doubles (NOT real capabilities)
# =====================================================================
class _CompletingCapability(ExecutionCapability):
    def execute(self, request):
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status="COMPLETED",
            capability_outputs={},
            execution_metadata={},
        )


class _RaisingCapability(ExecutionCapability):
    def execute(self, request):
        raise RuntimeError("provider boom")


# =====================================================================
# Helpers
# =====================================================================
_ORCH = None


def _orchestration():
    global _ORCH
    if _ORCH is None:
        _ORCH = get_execution_orchestration_engine().create_execution_orchestration(
            PlanningRequest(user_request="plan a trip to Japan")
        )
    return _ORCH


def _full_runtime(capability=None):
    return ExecutionRuntime(
        task_dispatcher=TaskDispatcher(),
        capability_dispatcher=CapabilityDispatcher(),
        capability_executor=CapabilityExecutor(capability or _CompletingCapability()),
        progress_runtime=ExecutionProgressRuntime(),
        controller=ExecutionController(),
        event_manager=ExecutionEventManager(),
        lifecycle_manager=ExecutionLifecycleManager(),
        state_manager=RuntimeExecutionStateManager(),
        monitor=RuntimeExecutionMonitor(),
        pause_resume_manager=RuntimePauseResumeManager(),
        recovery_coordinator=RuntimeRecoveryCoordinator(),
        resource_coordinator=RuntimeResourceCoordinator(),
    )


def _run(runtime=None, orchestration=None):
    runtime = runtime if runtime is not None else _full_runtime()
    return runtime.create_runtime_execution_orchestration(
        orchestration if orchestration is not None else _orchestration()
    )


def _ready_orchestration():
    """A Sprint 13 orchestration whose queue has a ready unit.

    The heuristic planner always gates (confirmation or capability blockers), so a
    real orchestration never dispatches a unit to a capability. Swapping in a
    ready queue (``NamedTuple._replace``) lets the real pipeline actually invoke
    the capability — needed to exercise provider-error propagation.
    """
    ready_unit = ExecutionUnit(
        unit_id="unit-1",
        step_number=1,
        description="d",
        execution_group=1,
        status="READY",
        dependencies=[],
        metadata={},
    )
    ready_queue = ExecutionQueue(
        queue_id="q",
        workflow_id="wf",
        status="READY",
        execution_units=[ready_unit],
        total_units=1,
        ready_units=1,
        blocked_units=0,
        metadata={},
    )
    return _orchestration()._replace(queue=ready_queue)


def _manual(runtime, orchestration):
    context = runtime.create_context(orchestration)
    dispatch_plan = runtime.task_dispatcher.create_dispatch_plan(context)
    capability_dispatch_plan = (
        runtime.capability_dispatcher.create_capability_dispatch_plan(dispatch_plan)
    )
    execution_summary = runtime.capability_executor.execute(capability_dispatch_plan)
    progress = runtime.progress_runtime.create_progress(execution_summary)
    control_state = runtime.controller.create_control_state(progress)
    event_log = runtime.event_manager.create_event_log(control_state)
    lifecycle = runtime.lifecycle_manager.create_lifecycle(event_log)
    state = runtime.state_manager.create_state(lifecycle)
    health = runtime.monitor.create_health(state)
    pause_resume = runtime.pause_resume_manager.create_pause_resume_state(health)
    recovery = runtime.recovery_coordinator.create_recovery_state(pause_resume)
    resource = runtime.resource_coordinator.create_resource_state(recovery)
    return {
        "context": context, "dispatch_plan": dispatch_plan,
        "capability_dispatch_plan": capability_dispatch_plan,
        "execution_summary": execution_summary, "progress": progress,
        "control_state": control_state, "event_log": event_log,
        "lifecycle": lifecycle, "state": state, "health": health,
        "pause_resume": pause_resume, "recovery": recovery, "resource": resource,
    }


def _record_order(runtime):
    order = []
    targets = [
        (runtime, "create_context"),
        (runtime.task_dispatcher, "create_dispatch_plan"),
        (runtime.capability_dispatcher, "create_capability_dispatch_plan"),
        (runtime.capability_executor, "execute"),
        (runtime.progress_runtime, "create_progress"),
        (runtime.controller, "create_control_state"),
        (runtime.event_manager, "create_event_log"),
        (runtime.lifecycle_manager, "create_lifecycle"),
        (runtime.state_manager, "create_state"),
        (runtime.monitor, "create_health"),
        (runtime.pause_resume_manager, "create_pause_resume_state"),
        (runtime.recovery_coordinator, "create_recovery_state"),
        (runtime.resource_coordinator, "create_resource_state"),
    ]
    for obj, name in targets:
        original = getattr(obj, name)

        def make(stage_name, orig):
            def wrapper(*args, **kwargs):
                order.append(stage_name)
                return orig(*args, **kwargs)
            return wrapper

        setattr(obj, name, make(name, original))
    return order


# =====================================================================
# End-to-end pipeline
# =====================================================================
class EndToEndPipelineTests(unittest.TestCase):
    def setUp(self):
        self.result = _run()

    def test_returns_runtime_orchestration_result(self):
        self.assertIsInstance(self.result, RuntimeExecutionOrchestrationResult)
        self.assertEqual(len(self.result), 13)

    def test_every_stage_output_has_the_right_type(self):
        for field, dto_type in RESULT_TYPES:
            with self.subTest(field=field):
                self.assertIsInstance(getattr(self.result, field), dto_type)

    def test_stages_chained_by_ids(self):
        r = self.result
        runtime_id = r.context.runtime_id
        execution_id = r.context.execution_id
        for field, _ in RESULT_TYPES:
            stage = getattr(r, field)
            with self.subTest(field=field):
                self.assertEqual(stage.runtime_id, runtime_id)
                self.assertEqual(stage.execution_id, execution_id)


# =====================================================================
# Deterministic outputs
# =====================================================================
class DeterminismTests(unittest.TestCase):
    def test_same_inputs_same_result(self):
        runtime = _full_runtime()
        self.assertEqual(_run(runtime), _run(runtime))

    def test_independent_runtimes_agree(self):
        self.assertEqual(_run(_full_runtime()), _run(_full_runtime()))


# =====================================================================
# Stage ordering & no stage skipped
# =====================================================================
class StageOrderingTests(unittest.TestCase):
    def test_runs_every_stage_in_order(self):
        runtime = _full_runtime()
        order = _record_order(runtime)
        runtime.create_runtime_execution_orchestration(_orchestration())
        self.assertEqual(order, STAGES)

    def test_no_stage_skipped(self):
        runtime = _full_runtime()
        order = _record_order(runtime)
        runtime.create_runtime_execution_orchestration(_orchestration())
        self.assertEqual(len(order), len(STAGES))
        self.assertEqual(set(order), set(STAGES))

    def test_each_stage_runs_exactly_once(self):
        runtime = _full_runtime()
        order = _record_order(runtime)
        runtime.create_runtime_execution_orchestration(_orchestration())
        for stage in STAGES:
            self.assertEqual(order.count(stage), 1)


# =====================================================================
# Failure propagation
# =====================================================================
class FailurePropagationTests(unittest.TestCase):
    def test_missing_collaborator_on_bare_runtime(self):
        with self.assertRaises(RuntimeError):
            ExecutionRuntime().create_runtime_execution_orchestration(
                _orchestration()
            )

    def test_missing_single_collaborator_propagates(self):
        runtime = _full_runtime()
        del runtime.monitor
        with self.assertRaises(RuntimeError):
            runtime.create_runtime_execution_orchestration(_orchestration())

    def test_provider_error_propagates(self):
        # A ready queue makes the executor actually invoke the capability, so the
        # raising capability's error propagates unchanged through the pipeline.
        runtime = _full_runtime(_RaisingCapability())
        with self.assertRaises(RuntimeError) as ctx:
            runtime.create_runtime_execution_orchestration(_ready_orchestration())
        self.assertEqual(str(ctx.exception), "provider boom")

    def test_validation_error_propagates(self):
        try:
            DispatchPlan(runtime_id="r")  # missing required fields
        except ValidationError as error:
            validation_error = error
        runtime = _full_runtime()
        runtime.task_dispatcher = MagicMock()
        runtime.task_dispatcher.create_dispatch_plan.side_effect = validation_error
        with self.assertRaises(ValidationError):
            runtime.create_runtime_execution_orchestration(_orchestration())


# =====================================================================
# No mutation between stages
# =====================================================================
class NoMutationTests(unittest.TestCase):
    def setUp(self):
        self.runtime = _full_runtime()
        self.result = _run(self.runtime)

    def test_result_dtos_are_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.context.runtime_status = "READY"
        with self.assertRaises(ValidationError):
            self.result.resource.resource_status = "BLOCKED"

    def test_result_container_is_immutable(self):
        with self.assertRaises(AttributeError):
            self.result.context = None

    def test_rerunning_downstream_stages_is_stable(self):
        r = self.result
        self.assertEqual(
            self.runtime.monitor.create_health(r.state), r.health
        )
        self.assertEqual(
            self.runtime.recovery_coordinator.create_recovery_state(
                r.pause_resume
            ),
            r.recovery,
        )
        self.assertEqual(
            self.runtime.resource_coordinator.create_resource_state(r.recovery),
            r.resource,
        )


# =====================================================================
# Backward compatibility
# =====================================================================
class BackwardCompatibilityTests(unittest.TestCase):
    def test_orchestration_equals_manual_composition(self):
        runtime = _full_runtime()
        result = runtime.create_runtime_execution_orchestration(_orchestration())
        manual = _manual(_full_runtime(), _orchestration())
        for field, _ in RESULT_TYPES:
            with self.subTest(field=field):
                self.assertEqual(getattr(result, field), manual[field])

    def test_bare_runtime_still_stateless(self):
        self.assertEqual(vars(ExecutionRuntime()), {})

    def test_bare_runtime_create_context_still_works(self):
        context = ExecutionRuntime().create_context(_orchestration())
        self.assertEqual(context.runtime_status, "INITIALIZED")

    def test_full_runtime_holds_all_collaborators(self):
        self.assertEqual(set(vars(_full_runtime())), FULL_ATTRS)


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class OrchestratorDependencyTests(unittest.TestCase):
    def test_provider_wires_runtime(self):
        from app.core.dependencies import get_runtime_execution_orchestrator

        runtime = get_runtime_execution_orchestrator(
            CapabilityExecutor(_CompletingCapability())
        )
        self.assertIsInstance(runtime, ExecutionRuntime)
        self.assertEqual(set(vars(runtime)), FULL_ATTRS)

    def test_provider_runs_pipeline(self):
        from app.core.dependencies import get_runtime_execution_orchestrator

        runtime = get_runtime_execution_orchestrator(
            CapabilityExecutor(_CompletingCapability())
        )
        result = runtime.create_runtime_execution_orchestration(_orchestration())
        self.assertIsInstance(result, RuntimeExecutionOrchestrationResult)

    def test_dep_alias_exists(self):
        from app.core.dependencies import RuntimeExecutionOrchestratorDep

        self.assertIsNotNone(RuntimeExecutionOrchestratorDep)

    def test_capability_seam_gates_full_di(self):
        # The orchestrator injects the executor through the 14.3 seam, which stays
        # unfulfilled until a concrete capability is wired.
        from app.core.dependencies import get_execution_capability

        with self.assertRaises(NotImplementedError):
            get_execution_capability()

    def test_existing_runtime_provider_unchanged(self):
        from app.core.dependencies import get_execution_runtime

        runtime = get_execution_runtime()
        self.assertIsInstance(runtime, ExecutionRuntime)
        self.assertEqual(vars(runtime), {})


# =====================================================================
# Regression: Sprint 14.1 context & Sprint 13 pipeline unchanged
# =====================================================================
class RegressionTests(unittest.TestCase):
    def test_create_context_unchanged(self):
        context = ExecutionRuntime().create_context(_orchestration())
        self.assertEqual(
            context.runtime_id, f"runtime-{_orchestration().state.execution_id}"
        )

    def test_orchestration_pipeline_unchanged(self):
        result = _orchestration()
        self.assertEqual(len(result), 14)
        self.assertEqual(result.plan.goal, "Plan your trip")


if __name__ == "__main__":
    unittest.main()
