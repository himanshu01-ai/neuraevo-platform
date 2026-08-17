"""Unit + integration tests for the Sprint 16.1 AI Employee Foundation.

Exercises :class:`AIEmployee` — the foundation that owns employee sessions and
task delegation and *orchestrates* the existing Planning Engine and Workflow
Coordinator (it plans nothing and executes no capability itself). No network or
SDK: the Planning Engine is the real deterministic heuristic engine, and the
Workflow Coordinator runs over an offline, deterministic stub
:class:`ExecutionCapability` (exactly the provider-independence the router relies
on). Recording doubles isolate the foundation to assert *invocation* precisely.

Covers, as the sprint requires:

* employee creation (the immutable profile / delegation DTOs);
* session lifecycle (``PENDING`` -> ``RUNNING`` -> ``COMPLETED``/``FAILED``);
* task delegation (end-to-end coordination + deterministic result);
* planning invocation (the Planning Engine is called with the task);
* workflow invocation (the Workflow Coordinator is called with the given steps);
* DI wiring (the composition-root ``get_ai_employee`` seam + ``AIEmployeeDep``);
* immutability (every DTO is frozen); and
* regression (the Sprint 13 Planning and Sprint 15.15 Workflow behaviour, and the
  existing composition-root providers, are unchanged).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_ai_employee
"""

import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    AIEmployee,
    EmployeeContext,
    EmployeeExecutionResult,
    EmployeeProfile,
    EmployeeSession,
    EmployeeSessionStatus,
    TaskDelegation,
    TaskPriority,
)
from app.services.planning.models import (
    ExecutionPlan,
    PlanningRequest,
)
from app.services.planning.planning_engine import PlanningEngine
from app.services.runtime.artifact_coordinator import ArtifactCoordinator
from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

_COMPLETED = CapabilityExecutionStatus.COMPLETED.value
_FAILED = CapabilityExecutionStatus.FAILED.value


# =====================================================================
# Offline capability doubles (NOT real capabilities)
# =====================================================================
class _CompletingCapability(ExecutionCapability):
    """Deterministic offline capability that always completes."""

    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_COMPLETED,
            capability_outputs={"ok": True},
            execution_metadata={},
        )


class _FailingCapability(ExecutionCapability):
    """Deterministic offline capability that always fails."""

    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=_FAILED,
            capability_outputs={"error": "boom"},
            execution_metadata={},
        )


# =====================================================================
# Recording doubles for the two collaborators (assert invocation)
# =====================================================================
def _make_plan() -> ExecutionPlan:
    return ExecutionPlan(goal="reason about it", summary="a plan")


def _make_workflow_result(status: str) -> WorkflowExecutionResult:
    return WorkflowExecutionResult(
        workflow_id="wf", workflow_status=status, total_step_count=1
    )


class _RecordingPlanningEngine:
    """Records every ``create_plan`` call; returns a fixed plan.

    Duck-types the one :class:`PlanningEngine` method the foundation uses, so the
    test can assert *what* the foundation asked the Planning Engine to reason
    about without invoking the real heuristic provider.
    """

    def __init__(self, plan=None):
        self._plan = plan if plan is not None else _make_plan()
        self.requests = []

    def create_plan(self, request: PlanningRequest) -> ExecutionPlan:
        self.requests.append(request)
        return self._plan


class _RecordingWorkflowCoordinator:
    """Records every ``execute`` call; returns a fixed workflow result."""

    def __init__(self, result: WorkflowExecutionResult):
        self._result = result
        self.calls = []

    def execute(
        self,
        steps,
        workflow_id="workflow",
        runtime_id="",
        execution_id="",
        initial_inputs=None,
    ) -> WorkflowExecutionResult:
        self.calls.append(
            {
                "steps": steps,
                "workflow_id": workflow_id,
                "runtime_id": runtime_id,
                "execution_id": execution_id,
                "initial_inputs": initial_inputs,
            }
        )
        return self._result


# =====================================================================
# Helpers
# =====================================================================
def _profile() -> EmployeeProfile:
    return EmployeeProfile(
        employee_id="e1", name="Ada", role="assistant", capabilities=["python"]
    )


def _delegation() -> TaskDelegation:
    return TaskDelegation(
        task_id="t1", task="plan a trip to Japan", priority=TaskPriority.HIGH
    )


def _steps():
    return [WorkflowStep(step_id="s1", capability_name="demo", inputs={"x": 1})]


def _recording_employee(workflow_status=WorkflowStatus.COMPLETED.value):
    planning = _RecordingPlanningEngine()
    coordinator = _RecordingWorkflowCoordinator(
        _make_workflow_result(workflow_status)
    )
    return AIEmployee(planning, coordinator), planning, coordinator


def _real_employee(capability=None):
    """AIEmployee over the REAL Planning Engine and REAL Workflow Coordinator."""
    from app.core.dependencies import get_execution_orchestration_engine

    router = CapabilityRouter({"demo": capability or _CompletingCapability()})
    coordinator = WorkflowCoordinator(router, ArtifactCoordinator())
    return AIEmployee(get_execution_orchestration_engine(), coordinator)


# =====================================================================
# Employee creation (immutable DTOs)
# =====================================================================
class EmployeeCreationTests(unittest.TestCase):
    def test_profile_holds_identity_and_defaults(self):
        profile = _profile()
        self.assertEqual(profile.employee_id, "e1")
        self.assertEqual(profile.name, "Ada")
        self.assertEqual(profile.capabilities, ["python"])
        self.assertEqual(profile.profile_metadata, {})

    def test_profile_requires_non_empty_id_and_name(self):
        with self.assertRaises(ValidationError):
            EmployeeProfile(employee_id="", name="Ada")
        with self.assertRaises(ValidationError):
            EmployeeProfile(employee_id="e1", name="   ")

    def test_delegation_defaults_priority_to_normal(self):
        delegation = TaskDelegation(task_id="t1", task="do it")
        self.assertEqual(delegation.priority, TaskPriority.NORMAL)
        self.assertEqual(delegation.constraints, [])

    def test_delegation_requires_non_empty_task(self):
        with self.assertRaises(ValidationError):
            TaskDelegation(task_id="t1", task="")


# =====================================================================
# Session lifecycle
# =====================================================================
class SessionLifecycleTests(unittest.TestCase):
    def test_default_session_status_is_pending(self):
        # A session constructed without a status starts PENDING (created, not
        # started) — the foundation moves it to RUNNING when a delegation starts.
        session = EmployeeSession(
            session_id="s", employee_id="e1", task_id="t1"
        )
        self.assertEqual(session.status, EmployeeSessionStatus.PENDING)

    def test_start_session_is_running_with_derived_ids(self):
        employee, _, _ = _recording_employee()
        session = employee.start_session(_profile(), _delegation())
        self.assertEqual(session.status, EmployeeSessionStatus.RUNNING)
        self.assertEqual(session.session_id, "session-e1-t1")
        self.assertEqual(session.employee_id, "e1")
        self.assertEqual(session.task_id, "t1")
        self.assertEqual(session.active_workflow_id, "workflow-t1")
        self.assertEqual(session.started_at_sequence, 0)
        self.assertIsNone(session.completed_at_sequence)

    def test_delegate_completes_session_on_workflow_success(self):
        employee, _, _ = _recording_employee(WorkflowStatus.COMPLETED.value)
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(result.status, EmployeeSessionStatus.COMPLETED)
        self.assertEqual(result.session.status, EmployeeSessionStatus.COMPLETED)
        self.assertEqual(result.session.completed_at_sequence, 1)

    def test_delegate_fails_session_on_workflow_failure(self):
        employee, _, _ = _recording_employee(WorkflowStatus.FAILED.value)
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(result.status, EmployeeSessionStatus.FAILED)
        self.assertEqual(result.session.status, EmployeeSessionStatus.FAILED)
        self.assertEqual(result.session.completed_at_sequence, 1)

    def test_context_snapshot_is_the_running_session(self):
        # The bound context captures the bind-time RUNNING session; the result's
        # top-level session is the terminal one.
        employee, _, _ = _recording_employee(WorkflowStatus.COMPLETED.value)
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(
            result.context.session.status, EmployeeSessionStatus.RUNNING
        )
        self.assertEqual(result.session.status, EmployeeSessionStatus.COMPLETED)


# =====================================================================
# Employee context
# =====================================================================
class EmployeeContextTests(unittest.TestCase):
    def test_context_binds_profile_and_session(self):
        employee, _, _ = _recording_employee()
        session = employee.start_session(_profile(), _delegation())
        context = employee.create_context(_profile(), session)
        self.assertEqual(context.employee_id, "e1")
        self.assertEqual(context.profile, _profile())
        self.assertEqual(context.session, session)

    def test_runtime_references_are_plain_string_descriptors(self):
        # No live collaborator or SDK object may cross the boundary — only names.
        employee, _, _ = _recording_employee()
        session = employee.start_session(_profile(), _delegation())
        context = employee.create_context(_profile(), session)
        self.assertEqual(
            set(context.runtime_references), {"planning_engine", "workflow_coordinator"}
        )
        for value in context.runtime_references.values():
            self.assertIsInstance(value, str)

    def test_real_context_names_the_real_collaborators(self):
        employee = _real_employee()
        session = employee.start_session(_profile(), _delegation())
        context = employee.create_context(_profile(), session)
        self.assertEqual(
            context.runtime_references["planning_engine"], "PlanningEngine"
        )
        self.assertEqual(
            context.runtime_references["workflow_coordinator"],
            "WorkflowCoordinator",
        )


# =====================================================================
# Task delegation (end-to-end)
# =====================================================================
class TaskDelegationTests(unittest.TestCase):
    def test_delegate_returns_execution_result(self):
        employee, _, _ = _recording_employee()
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertIsInstance(result, EmployeeExecutionResult)
        self.assertEqual(result.employee_id, "e1")
        self.assertEqual(result.session_id, "session-e1-t1")
        self.assertEqual(result.task_id, "t1")

    def test_result_carries_plan_and_workflow_result(self):
        employee, planning, coordinator = _recording_employee()
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertIs(result.plan, planning._plan)
        self.assertIs(result.workflow_result, coordinator._result)

    def test_result_metadata_summarises_outcome(self):
        employee, _, _ = _recording_employee(WorkflowStatus.COMPLETED.value)
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(
            result.result_metadata["workflow_status"],
            WorkflowStatus.COMPLETED.value,
        )
        self.assertIn("planned_step_count", result.result_metadata)

    def test_delegate_is_deterministic(self):
        employee, _, _ = _recording_employee()
        first = employee.delegate(_profile(), _delegation(), _steps())
        second = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(first, second)

    def test_real_end_to_end_completes(self):
        # REAL Planning Engine + REAL Workflow Coordinator over a completing stub.
        employee = _real_employee(_CompletingCapability())
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(result.status, EmployeeSessionStatus.COMPLETED)
        self.assertEqual(
            result.workflow_result.workflow_status,
            WorkflowStatus.COMPLETED.value,
        )
        self.assertIsInstance(result.plan, ExecutionPlan)
        self.assertTrue(result.plan.goal)

    def test_real_end_to_end_fails_gracefully(self):
        # A failing capability yields a graceful FAILED result — never a raise.
        employee = _real_employee(_FailingCapability())
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(result.status, EmployeeSessionStatus.FAILED)
        self.assertEqual(
            result.workflow_result.workflow_status, WorkflowStatus.FAILED.value
        )


# =====================================================================
# Planning invocation
# =====================================================================
class PlanningInvocationTests(unittest.TestCase):
    def test_planning_engine_called_once_with_the_task(self):
        employee, planning, _ = _recording_employee()
        employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(len(planning.requests), 1)
        request = planning.requests[0]
        self.assertIsInstance(request, PlanningRequest)
        self.assertEqual(request.user_request, "plan a trip to Japan")

    def test_coordinate_planning_returns_plan(self):
        employee, planning, _ = _recording_employee()
        plan = employee._coordinate_planning(_delegation())
        self.assertIs(plan, planning._plan)


# =====================================================================
# Workflow invocation
# =====================================================================
class WorkflowInvocationTests(unittest.TestCase):
    def test_workflow_coordinator_called_with_given_steps(self):
        employee, _, coordinator = _recording_employee()
        steps = _steps()
        employee.delegate(_profile(), _delegation(), steps)
        self.assertEqual(len(coordinator.calls), 1)
        call = coordinator.calls[0]
        self.assertIs(call["steps"], steps)

    def test_workflow_ids_derived_from_session(self):
        employee, _, coordinator = _recording_employee()
        employee.delegate(_profile(), _delegation(), _steps())
        call = coordinator.calls[0]
        self.assertEqual(call["workflow_id"], "workflow-t1")
        self.assertEqual(call["runtime_id"], "session-e1-t1")
        self.assertEqual(call["execution_id"], "session-e1-t1")

    def test_initial_inputs_are_forwarded(self):
        employee, _, coordinator = _recording_employee()
        employee.delegate(
            _profile(), _delegation(), _steps(), initial_inputs={"seed": 1}
        )
        self.assertEqual(coordinator.calls[0]["initial_inputs"], {"seed": 1})

    def test_foundation_never_dispatches_a_capability_directly(self):
        # The foundation reaches capabilities ONLY through the coordinator. It
        # exposes exactly the two collaborators and no capability/router handle.
        employee, _, _ = _recording_employee()
        self.assertEqual(
            set(vars(employee)), {"planning_engine", "workflow_coordinator"}
        )


# =====================================================================
# Immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        employee, _, _ = _recording_employee()
        self.result = employee.delegate(_profile(), _delegation(), _steps())

    def test_profile_is_frozen(self):
        with self.assertRaises(ValidationError):
            _profile().name = "Bob"

    def test_delegation_is_frozen(self):
        with self.assertRaises(ValidationError):
            _delegation().task = "changed"

    def test_session_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.session.status = EmployeeSessionStatus.PENDING

    def test_context_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.context.employee_id = "other"

    def test_result_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.status = EmployeeSessionStatus.PENDING


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_provider_wires_the_two_collaborators(self):
        from app.core.dependencies import get_ai_employee

        employee = get_ai_employee()
        self.assertIsInstance(employee, AIEmployee)
        self.assertIsInstance(employee.planning_engine, PlanningEngine)
        self.assertIsInstance(employee.workflow_coordinator, WorkflowCoordinator)

    def test_provider_uses_injected_collaborators_when_supplied(self):
        from app.core.dependencies import get_ai_employee

        planning = _RecordingPlanningEngine()
        coordinator = _RecordingWorkflowCoordinator(
            _make_workflow_result(WorkflowStatus.COMPLETED.value)
        )
        employee = get_ai_employee(planning, coordinator)
        self.assertIs(employee.planning_engine, planning)
        self.assertIs(employee.workflow_coordinator, coordinator)

    def test_dep_alias_exists(self):
        from app.core.dependencies import AIEmployeeDep

        self.assertIsNotNone(AIEmployeeDep)

    def test_wired_employee_runs_a_delegation(self):
        from app.core.dependencies import get_ai_employee

        employee = get_ai_employee()
        # Swap the coordinator for a completing-stub one so the real end-to-end
        # path yields COMPLETED deterministically and offline.
        employee.workflow_coordinator = WorkflowCoordinator(
            CapabilityRouter({"demo": _CompletingCapability()}),
            ArtifactCoordinator(),
        )
        result = employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(result.status, EmployeeSessionStatus.COMPLETED)


# =====================================================================
# Regression: Planning / Workflow / existing providers unchanged
# =====================================================================
class RegressionTests(unittest.TestCase):
    def test_planning_engine_still_reasons(self):
        from app.core.dependencies import get_execution_orchestration_engine

        plan = get_execution_orchestration_engine().create_plan(
            PlanningRequest(user_request="plan a trip to Japan")
        )
        self.assertEqual(plan.goal, "Plan your trip")

    def test_workflow_coordinator_still_runs_steps(self):
        coordinator = WorkflowCoordinator(
            CapabilityRouter({"demo": _CompletingCapability()}),
            ArtifactCoordinator(),
        )
        result = coordinator.execute(
            [WorkflowStep(step_id="s1", capability_name="demo")]
        )
        self.assertEqual(
            result.workflow_status, WorkflowStatus.COMPLETED.value
        )

    def test_existing_workflow_coordinator_provider_unchanged(self):
        from app.core.dependencies import get_workflow_coordinator

        coordinator = get_workflow_coordinator()
        self.assertIsInstance(coordinator, WorkflowCoordinator)

    def test_foundation_adds_no_state_to_collaborators(self):
        # The foundation only reads the two collaborators; it stores no session,
        # cache, or capability handle of its own between calls.
        employee, _, _ = _recording_employee()
        employee.delegate(_profile(), _delegation(), _steps())
        self.assertEqual(
            set(vars(employee)), {"planning_engine", "workflow_coordinator"}
        )


if __name__ == "__main__":
    unittest.main()
