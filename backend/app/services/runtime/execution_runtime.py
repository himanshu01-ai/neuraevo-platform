"""Execution runtime (Sprint 14.1 — context; Sprint 14.15 — orchestration).

Owns the lifecycle of one execution session. In Sprint 14.1 it consumes a Sprint
13 :class:`ExecutionOrchestrationResult` and establishes an immutable
:class:`ExecutionRuntimeContext` for it. In Sprint 14.15 it also becomes the
single runtime orchestration coordinator: ``create_runtime_execution_orchestration``
runs every Sprint 14 runtime stage in order by delegating to injected
collaborators, adding no new runtime logic of its own.

It never dispatches, executes, recovers, approves, or performs any networking or
I/O directly — each stage does its own work behind its own method, and this
runtime only coordinates. Fully deterministic and offline: no AI, network, clock,
UUID, SDK, Runtime global, or persistence. Same inputs in -> same outputs out.
"""

from typing import NamedTuple, Optional

from app.services.planning.planning_engine import ExecutionOrchestrationResult
from app.services.runtime.capability_dispatcher import CapabilityDispatcher
from app.services.runtime.capability_dispatcher_models import (
    CapabilityDispatchPlan,
)
from app.services.runtime.capability_executor import CapabilityExecutor
from app.services.runtime.capability_executor_models import (
    CapabilityExecutionSummary,
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
from app.services.runtime.execution_runtime_models import (
    ExecutionRuntimeContext,
    ExecutionRuntimeStatus,
)
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

# The genesis sequence position of a freshly initialized runtime session. It is a
# fixed, deterministic ordinal — never a clock time and never a global counter
# (the runtime is stateless) — so one orchestration always yields one identical
# context.
_GENESIS_SEQUENCE = 0


class RuntimeExecutionOrchestrationResult(NamedTuple):
    """Immutable, provider-independent aggregation of the runtime pipeline (14.15).

    A single result that carries every Sprint 14 runtime stage output in order,
    from the runtime context through to the resource state. This is NOT a new DTO:
    it is a plain, immutable :class:`typing.NamedTuple` container of the *existing*
    frozen runtime DTOs, introducing no new model, no validation, and no
    behaviour. It only names what each already-validated stage produced so a
    caller can read the whole runtime pipeline from one value. Nothing here
    executes or mutates anything.
    """

    context: ExecutionRuntimeContext
    dispatch_plan: DispatchPlan
    capability_dispatch_plan: CapabilityDispatchPlan
    execution_summary: CapabilityExecutionSummary
    progress: ExecutionProgress
    control_state: ExecutionControlState
    event_log: ExecutionEventLog
    lifecycle: RuntimeExecutionLifecycle
    state: RuntimeExecutionState
    health: RuntimeExecutionHealth
    pause_resume: RuntimePauseResumeState
    recovery: RuntimeRecoveryState
    resource: RuntimeResourceState


class ExecutionRuntime:
    """Runtime session owner and Sprint 14 orchestration coordinator.

    Creates an immutable :class:`ExecutionRuntimeContext` per orchestration
    (status ``INITIALIZED``, no current unit, empty stores, deterministic id).
    When the twelve Sprint 14 runtime collaborators are injected, it also
    coordinates the full runtime pipeline via
    ``create_runtime_execution_orchestration`` — delegating to each collaborator's
    existing method in order, adding no runtime logic. Stateless beyond the
    injected collaborator references; it dispatches, executes, recovers, approves,
    and performs I/O only through those collaborators (or not at all), and never
    modifies the orchestration or any stage output.
    """

    def __init__(
        self,
        task_dispatcher: Optional[TaskDispatcher] = None,
        capability_dispatcher: Optional[CapabilityDispatcher] = None,
        capability_executor: Optional[CapabilityExecutor] = None,
        progress_runtime: Optional[ExecutionProgressRuntime] = None,
        controller: Optional[ExecutionController] = None,
        event_manager: Optional[ExecutionEventManager] = None,
        lifecycle_manager: Optional[ExecutionLifecycleManager] = None,
        state_manager: Optional[RuntimeExecutionStateManager] = None,
        monitor: Optional[RuntimeExecutionMonitor] = None,
        pause_resume_manager: Optional[RuntimePauseResumeManager] = None,
        recovery_coordinator: Optional[RuntimeRecoveryCoordinator] = None,
        resource_coordinator: Optional[RuntimeResourceCoordinator] = None,
    ) -> None:
        # Sprint 14.15 integration: the twelve runtime collaborators are optional,
        # additive references stored only when injected — so a bare
        # ``ExecutionRuntime()`` (Sprint 14.1) keeps exactly its original (empty)
        # attribute set and its ``create_context`` path unchanged.
        # ``create_runtime_execution_orchestration`` requires the full set;
        # ``create_context`` requires none.
        if task_dispatcher is not None:
            self.task_dispatcher = task_dispatcher
        if capability_dispatcher is not None:
            self.capability_dispatcher = capability_dispatcher
        if capability_executor is not None:
            self.capability_executor = capability_executor
        if progress_runtime is not None:
            self.progress_runtime = progress_runtime
        if controller is not None:
            self.controller = controller
        if event_manager is not None:
            self.event_manager = event_manager
        if lifecycle_manager is not None:
            self.lifecycle_manager = lifecycle_manager
        if state_manager is not None:
            self.state_manager = state_manager
        if monitor is not None:
            self.monitor = monitor
        if pause_resume_manager is not None:
            self.pause_resume_manager = pause_resume_manager
        if recovery_coordinator is not None:
            self.recovery_coordinator = recovery_coordinator
        if resource_coordinator is not None:
            self.resource_coordinator = resource_coordinator

    def create_context(
        self, orchestration: ExecutionOrchestrationResult
    ) -> ExecutionRuntimeContext:
        """Return a deterministic :class:`ExecutionRuntimeContext` (no execution).

        The runtime id is derived from the orchestration's execution id; the
        status is always ``INITIALIZED``; the orchestration is stored unchanged;
        the current unit is ``None``; and the runtime variable, output, and
        metadata stores start empty. The orchestration is only read — never
        modified — and nothing is executed, dispatched, recovered, or approved.
        """
        execution_id = orchestration.state.execution_id
        return ExecutionRuntimeContext(
            runtime_id=f"runtime-{execution_id}",
            execution_id=execution_id,
            runtime_status=ExecutionRuntimeStatus.INITIALIZED.value,
            orchestration=orchestration,
            current_execution_unit_id=None,
            execution_variables={},
            execution_outputs={},
            execution_metadata={},
            created_at_sequence=_GENESIS_SEQUENCE,
            metadata={
                "total_execution_units": len(
                    orchestration.queue.execution_units
                ),
                "source_execution_id": execution_id,
            },
        )

    def create_runtime_execution_orchestration(
        self, orchestration: ExecutionOrchestrationResult
    ) -> RuntimeExecutionOrchestrationResult:
        """Coordinate the complete Sprint 14 runtime pipeline (no new logic).

        Sprint 14.15 integration — this is the single runtime orchestration
        coordinator. It runs every existing runtime stage in order by delegating
        to this runtime's own ``create_context`` and the injected collaborators'
        methods, each of which keeps its own validation:

            orchestration -> context -> dispatch plan -> capability dispatch plan
            -> execution summary -> progress -> control state -> event log ->
            lifecycle -> state -> health -> pause/resume -> recovery -> resource

        No stage is skipped and no stage is executed here directly; each stage only
        reads the immutable output of the previous stage, so nothing is mutated
        between stages. Returns one immutable
        :class:`RuntimeExecutionOrchestrationResult` built entirely from the
        existing runtime DTOs. A missing collaborator raises :class:`RuntimeError`;
        collaborator/validation exceptions propagate unchanged, so a failure at any
        stage aborts the whole pipeline.
        """
        context = self.create_context(orchestration)
        dispatch_plan = self._collaborator(
            "task_dispatcher"
        ).create_dispatch_plan(context)
        capability_dispatch_plan = self._collaborator(
            "capability_dispatcher"
        ).create_capability_dispatch_plan(dispatch_plan)
        execution_summary = self._collaborator(
            "capability_executor"
        ).execute(capability_dispatch_plan)
        progress = self._collaborator("progress_runtime").create_progress(
            execution_summary
        )
        control_state = self._collaborator(
            "controller"
        ).create_control_state(progress)
        event_log = self._collaborator("event_manager").create_event_log(
            control_state
        )
        lifecycle = self._collaborator(
            "lifecycle_manager"
        ).create_lifecycle(event_log)
        state = self._collaborator("state_manager").create_state(lifecycle)
        health = self._collaborator("monitor").create_health(state)
        pause_resume = self._collaborator(
            "pause_resume_manager"
        ).create_pause_resume_state(health)
        recovery = self._collaborator(
            "recovery_coordinator"
        ).create_recovery_state(pause_resume)
        resource = self._collaborator(
            "resource_coordinator"
        ).create_resource_state(recovery)

        return RuntimeExecutionOrchestrationResult(
            context=context,
            dispatch_plan=dispatch_plan,
            capability_dispatch_plan=capability_dispatch_plan,
            execution_summary=execution_summary,
            progress=progress,
            control_state=control_state,
            event_log=event_log,
            lifecycle=lifecycle,
            state=state,
            health=health,
            pause_resume=pause_resume,
            recovery=recovery,
            resource=resource,
        )

    def _collaborator(self, name: str):
        """Return the injected collaborator ``name`` or raise if it is missing."""
        collaborator = getattr(self, name, None)
        if collaborator is None:
            raise RuntimeError(
                f"ExecutionRuntime has no {name} injected; provide the full "
                "runtime collaborator set to call "
                "create_runtime_execution_orchestration()."
            )
        return collaborator
