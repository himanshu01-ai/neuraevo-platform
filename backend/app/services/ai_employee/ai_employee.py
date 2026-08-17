"""AI Employee (Sprint 16.1 — the AI Employee Foundation; orchestrate, never do).

Defines :class:`AIEmployee`, the foundation layer that *owns employee sessions
and task delegation* and *coordinates the existing systems*. It follows the
locked flow:

    AIEmployee -> EmployeeSession -> EmployeeContext -> TaskDelegation ->
    Planning Engine -> Workflow Coordinator

It accepts a delegated task, starts a deterministic :class:`EmployeeSession`,
binds an :class:`EmployeeContext`, coordinates the Planning Engine to *reason*
about the task (producing an :class:`ExecutionPlan`), coordinates the Workflow
Coordinator to *execute* the given workflow steps (producing a
:class:`WorkflowExecutionResult`), and returns one immutable
:class:`EmployeeExecutionResult`.

It plans nothing, executes no capability, and never touches Runtime, Memory,
Permission, or Capability internals directly — it only uses the two injected
collaborators through their existing public contracts. Constructor injection
only; stateless beyond the two collaborator references (no static, singleton, or
service-locator state); fully deterministic (no clock, UUID, network, or SDK).
Strictly additive to Sprints 1.x–15.15, whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.models import (
    EmployeeContext,
    EmployeeExecutionResult,
    EmployeeProfile,
    EmployeeSession,
    EmployeeSessionStatus,
    TaskDelegation,
)
from app.services.planning.models import ExecutionPlan, PlanningRequest
from app.services.planning.planning_engine import PlanningEngine
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

# Deterministic session-timing ordinals — fixed integer positions, never clock
# times and never a global counter (the foundation is stateless), so one
# delegation always yields one identical session.
_SESSION_START_SEQUENCE = 0
_SESSION_COMPLETION_SEQUENCE = 1


class AIEmployee:
    """Owns employee sessions and delegation; orchestrates Planning and Workflow.

    Constructed with an injected :class:`PlanningEngine` and
    :class:`WorkflowCoordinator` (constructor injection; it instantiates
    neither). ``delegate`` starts a session, builds a context, coordinates
    planning, coordinates workflow execution, and returns a deterministic
    :class:`EmployeeExecutionResult`. It holds no mutable state between calls,
    performs no planning and no execution of its own, and reaches Runtime, Memory,
    Permission, and Capabilities only indirectly through the two collaborators.
    """

    def __init__(
        self,
        planning_engine: PlanningEngine,
        workflow_coordinator: WorkflowCoordinator,
    ) -> None:
        self.planning_engine = planning_engine
        self.workflow_coordinator = workflow_coordinator

    # --- lifecycle -------------------------------------------------------
    def start_session(
        self, profile: EmployeeProfile, delegation: TaskDelegation
    ) -> EmployeeSession:
        """Start a deterministic ``RUNNING`` :class:`EmployeeSession` (no execution).

        The session id and active workflow id are derived deterministically from
        the profile and delegation, the status is ``RUNNING``, and the start
        ordinal is fixed — so the same profile and delegation always yield the
        same session. Nothing is planned or executed here.
        """
        return EmployeeSession(
            session_id=self._session_id(profile, delegation),
            employee_id=profile.employee_id,
            task_id=delegation.task_id,
            status=EmployeeSessionStatus.RUNNING,
            active_workflow_id=self._workflow_id(delegation),
            started_at_sequence=_SESSION_START_SEQUENCE,
            completed_at_sequence=None,
            session_metadata={"priority": delegation.priority.value},
        )

    def create_context(
        self, profile: EmployeeProfile, session: EmployeeSession
    ) -> EmployeeContext:
        """Bind ``profile`` and ``session`` into an :class:`EmployeeContext`.

        The runtime references expose only the plain class names of the wired
        collaborators (never the live objects), so no provider/SDK object crosses
        this boundary. The profile and session are read, not modified, and nothing
        is executed.
        """
        return EmployeeContext(
            employee_id=profile.employee_id,
            profile=profile,
            session=session,
            runtime_references={
                "planning_engine": type(self.planning_engine).__name__,
                "workflow_coordinator": type(
                    self.workflow_coordinator
                ).__name__,
            },
            context_metadata={},
        )

    # --- orchestration ---------------------------------------------------
    def delegate(
        self,
        profile: EmployeeProfile,
        delegation: TaskDelegation,
        workflow_steps: List[WorkflowStep],
        initial_inputs: Optional[Dict[str, Any]] = None,
    ) -> EmployeeExecutionResult:
        """Coordinate one delegation end-to-end and return its result (no new work).

        Runs the locked flow by delegating to the two injected collaborators, each
        of which keeps its own contract:

            delegation -> session -> context -> plan (Planning Engine) ->
            workflow result (Workflow Coordinator) -> terminal session -> result

        It starts a session, binds a context, coordinates the Planning Engine to
        *reason* about ``delegation.task`` (producing an :class:`ExecutionPlan`),
        then coordinates the Workflow Coordinator to *execute* the given
        ``workflow_steps`` (producing a :class:`WorkflowExecutionResult`). The
        terminal session status mirrors the workflow outcome. The foundation plans
        nothing and executes no capability itself; the executable steps are given
        by the delegating layer, exactly as the Workflow Coordinator expects.
        Planning-provider/validator exceptions propagate unchanged; the Workflow
        Coordinator reports step failures as a graceful ``FAILED`` result rather
        than raising.
        """
        session = self.start_session(profile, delegation)
        # Bind profile + session + runtime references for this delegation. The
        # context is the layer's own record that the session is runtime-bound; it
        # is surfaced on the result rather than consumed downstream (Planning and
        # Workflow have their own inputs).
        context = self.create_context(profile, session)

        plan = self._coordinate_planning(delegation)
        workflow_result = self._coordinate_workflow(
            session, workflow_steps, initial_inputs
        )

        completed = (
            workflow_result.workflow_status == WorkflowStatus.COMPLETED.value
        )
        terminal_status = (
            EmployeeSessionStatus.COMPLETED
            if completed
            else EmployeeSessionStatus.FAILED
        )
        final_session = session.model_copy(
            update={
                "status": terminal_status,
                "completed_at_sequence": _SESSION_COMPLETION_SEQUENCE,
            }
        )

        return EmployeeExecutionResult(
            employee_id=profile.employee_id,
            session_id=session.session_id,
            task_id=delegation.task_id,
            status=terminal_status,
            context=context,
            plan=plan,
            workflow_result=workflow_result,
            session=final_session,
            result_metadata={
                "workflow_status": workflow_result.workflow_status,
                "planned_step_count": plan.estimated_step_count,
            },
        )

    # --- collaborators ---------------------------------------------------
    def _coordinate_planning(
        self, delegation: TaskDelegation
    ) -> ExecutionPlan:
        """Coordinate the Planning Engine to reason about the task (reasoning only)."""
        return self.planning_engine.create_plan(
            PlanningRequest(user_request=delegation.task)
        )

    def _coordinate_workflow(
        self,
        session: EmployeeSession,
        workflow_steps: List[WorkflowStep],
        initial_inputs: Optional[Dict[str, Any]],
    ) -> WorkflowExecutionResult:
        """Coordinate the Workflow Coordinator to execute the given steps."""
        return self.workflow_coordinator.execute(
            workflow_steps,
            workflow_id=session.active_workflow_id or session.session_id,
            runtime_id=session.session_id,
            execution_id=session.session_id,
            initial_inputs=initial_inputs,
        )

    # --- deterministic identity ------------------------------------------
    @staticmethod
    def _session_id(
        profile: EmployeeProfile, delegation: TaskDelegation
    ) -> str:
        """Derive the deterministic session id from the profile and delegation."""
        return f"session-{profile.employee_id}-{delegation.task_id}"

    @staticmethod
    def _workflow_id(delegation: TaskDelegation) -> str:
        """Derive the deterministic workflow id from the delegation."""
        return f"workflow-{delegation.task_id}"
