"""Unit + integration tests for the Sprint 16.10 AI Employee Service Layer.

Exercises the Service Layer subsystem: the :class:`SessionManager`, the
:class:`RequestValidator`, the :class:`ResponseBuilder`, the
:class:`IdempotencyManager`, the :class:`HealthManager`, the :class:`ErrorMapper`,
the deterministic task-lifecycle transitions, and the :class:`AIEmployeeService`
entry point that coordinates them and always delegates the running to the frozen
Sprint 16.1 :class:`AIEmployee`.

The Service Layer coordinates external requests; it executes no workflow or
capability itself and never surfaces a raw exception. Here the :class:`AIEmployee`
runs over deterministic recording doubles so a submission resolves to a fixed
``COMPLETED``/``FAILED`` outcome with no network or SDK.

Covers, as the sprint requires: task submission, session lifecycle, validation,
response contracts, idempotency, health, readiness, error mapping, service
delegation, DTO immutability, DI wiring, and regression (Sprints 16.1–16.9
unchanged; the service sub-package imports no Workflow Coordinator, capability,
repository, LLM provider, database, or web/transport facility).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_ai_employee_service_layer
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import AIEmployee, EmployeeProfile
from app.services.ai_employee.coordination.models import (
    AgentNotFoundError as CoordinationAgentNotFoundError,
)
from app.services.ai_employee.coordination.models import (
    TaskNotFoundError as CoordinationTaskNotFoundError,
)
from app.services.ai_employee.persistence.models import MissingWorkflowError
from app.services.ai_employee.scheduler.models import ScheduleNotFoundError
from app.services.ai_employee.service import (
    AIEmployeeService,
    ErrorMapper,
    HealthManager,
    HealthState,
    HealthStatus,
    IdempotencyManager,
    IdempotencyRecord,
    InvalidTaskTransitionException,
    RequestValidator,
    ResponseBuilder,
    ServiceError,
    ServiceErrorCode,
    SessionInfo,
    SessionManager,
    SessionNotFoundException,
    SessionStatus,
    TaskAction,
    TaskNotFoundException,
    TaskState,
    TaskStatusResponse,
    TaskSubmissionRequest,
    TaskSubmissionResponse,
    ValidationException,
    next_task_state,
)
from app.services.ai_employee.service.health import HEALTH_COMPONENTS
from app.services.planning.models import ExecutionPlan
from app.services.runtime.workflow_models import (
    WorkflowExecutionResult,
    WorkflowStatus,
    WorkflowStep,
)

_COMPLETED = WorkflowStatus.COMPLETED.value
_FAILED = WorkflowStatus.FAILED.value


# =====================================================================
# Offline recording doubles for the AIEmployee's collaborators
# =====================================================================
class _RecordingPlanningEngine:
    def create_plan(self, request) -> ExecutionPlan:
        return ExecutionPlan(goal="reason about it", summary="a plan")


class _RecordingWorkflowCoordinator:
    def __init__(self, status: str = _COMPLETED) -> None:
        self._status = status
        self.calls = []

    def execute(
        self,
        steps,
        workflow_id="workflow",
        runtime_id="",
        execution_id="",
        initial_inputs=None,
    ) -> WorkflowExecutionResult:
        self.calls.append({"steps": steps, "initial_inputs": initial_inputs})
        return WorkflowExecutionResult(
            workflow_id=workflow_id,
            workflow_status=self._status,
            total_step_count=len(steps),
        )


class _ExplodingAIEmployee:
    """AIEmployee double whose delegate always raises (delegation-failure path)."""

    def delegate(self, *args, **kwargs):
        raise RuntimeError("delegate boom")


# =====================================================================
# Helpers
# =====================================================================
def _ai_employee(status: str = _COMPLETED):
    workflow = _RecordingWorkflowCoordinator(status)
    return AIEmployee(_RecordingPlanningEngine(), workflow), workflow


def _healthy_components():
    return {name: True for name in HEALTH_COMPONENTS}


def _service(status: str = _COMPLETED, ai=None, health=None):
    ai_employee = ai
    workflow = None
    if ai_employee is None:
        ai_employee, workflow = _ai_employee(status)
    service = AIEmployeeService(
        ai_employee,
        SessionManager(),
        RequestValidator(),
        ResponseBuilder(),
        IdempotencyManager(),
        health or HealthManager(_healthy_components()),
        ErrorMapper(),
    )
    return service, workflow


def _request(
    request_id="r1",
    task_id="biz-1",
    task="write the report",
    steps=True,
    idempotency_key=None,
    employee_id="e1",
):
    return TaskSubmissionRequest(
        request_id=request_id,
        employee=EmployeeProfile(employee_id=employee_id, name="Ada"),
        task_id=task_id,
        task=task,
        workflow_steps=(
            [WorkflowStep(step_id="s1", capability_name="demo")]
            if steps
            else []
        ),
        idempotency_key=idempotency_key,
    )


# =====================================================================
# Task submission
# =====================================================================
class TaskSubmissionTests(unittest.TestCase):
    def test_submit_accepts_and_completes(self):
        service, _ = _service(_COMPLETED)
        response = service.submit_task(_request())
        self.assertIsInstance(response, TaskSubmissionResponse)
        self.assertTrue(response.accepted)
        self.assertEqual(response.state, TaskState.COMPLETED)
        self.assertTrue(response.task_id)
        self.assertTrue(response.session_id)
        self.assertIsNone(response.error)

    def test_submit_reports_failed_execution(self):
        service, _ = _service(_FAILED)
        response = service.submit_task(_request())
        self.assertTrue(response.accepted)
        self.assertEqual(response.state, TaskState.FAILED)

    def test_submit_opens_a_session(self):
        service, _ = _service()
        response = service.submit_task(_request())
        session = service.session_manager.load(response.session_id)
        self.assertEqual(session.status, SessionStatus.ACTIVE)

    def test_submit_delegates_to_ai_employee(self):
        service, workflow = _service()
        service.submit_task(_request())
        self.assertEqual(len(workflow.calls), 1)  # ran via the AIEmployee

    def test_delegation_failure_is_mapped_not_raised(self):
        service, _ = _service(ai=_ExplodingAIEmployee())
        response = service.submit_task(_request())
        self.assertFalse(response.accepted)
        self.assertIsNotNone(response.error)
        self.assertEqual(
            response.error.code, ServiceErrorCode.DELEGATION_FAILED
        )

    def test_delegation_failure_closes_session(self):
        service, _ = _service(ai=_ExplodingAIEmployee())
        service.submit_task(_request())
        # The one created session was closed on the failed delegation.
        self.assertEqual(service.session_manager.active(), [])


# =====================================================================
# Reads: get / list
# =====================================================================
class TaskReadTests(unittest.TestCase):
    def test_get_task_returns_status(self):
        service, _ = _service()
        submitted = service.submit_task(_request())
        status = service.get_task(submitted.task_id)
        self.assertIsInstance(status, TaskStatusResponse)
        self.assertEqual(status.state, TaskState.COMPLETED)
        self.assertTrue(status.success)
        self.assertEqual(status.result_summary["business_task_id"], "biz-1")

    def test_get_unknown_task_is_not_found(self):
        service, _ = _service()
        status = service.get_task("nope")
        self.assertIsNone(status.state)
        self.assertEqual(status.error.code, ServiceErrorCode.TASK_NOT_FOUND)

    def test_list_tasks_in_submission_order(self):
        service, _ = _service()
        first = service.submit_task(_request(request_id="r1", task_id="b1"))
        second = service.submit_task(_request(request_id="r2", task_id="b2"))
        listed = [t.task_id for t in service.list_tasks()]
        self.assertEqual(listed, [first.task_id, second.task_id])


# =====================================================================
# Lifecycle control (cancel / pause / resume)
# =====================================================================
class LifecycleControlTests(unittest.TestCase):
    def test_cancel_completed_task_withdraws_it(self):
        service, _ = _service(_COMPLETED)
        submitted = service.submit_task(_request())
        result = service.cancel_task(submitted.task_id)
        self.assertEqual(result.state, TaskState.CANCELLED)
        self.assertEqual(
            result.response_metadata["previous_state"], "COMPLETED"
        )

    def test_cancel_closes_the_session(self):
        service, _ = _service()
        submitted = service.submit_task(_request())
        service.cancel_task(submitted.task_id)
        session = service.session_manager.load(submitted.session_id)
        self.assertEqual(session.status, SessionStatus.CLOSED)

    def test_cancel_twice_is_not_cancellable(self):
        service, _ = _service()
        submitted = service.submit_task(_request())
        service.cancel_task(submitted.task_id)
        again = service.cancel_task(submitted.task_id)
        self.assertEqual(
            again.error.code, ServiceErrorCode.TASK_NOT_CANCELLABLE
        )
        self.assertEqual(again.state, TaskState.CANCELLED)  # unchanged

    def test_pause_completed_task_is_not_pausable(self):
        service, _ = _service()
        submitted = service.submit_task(_request())
        result = service.pause_task(submitted.task_id)
        self.assertEqual(
            result.error.code, ServiceErrorCode.TASK_NOT_PAUSABLE
        )
        self.assertEqual(result.state, TaskState.COMPLETED)  # unchanged

    def test_resume_completed_task_is_not_resumable(self):
        service, _ = _service()
        submitted = service.submit_task(_request())
        result = service.resume_task(submitted.task_id)
        self.assertEqual(
            result.error.code, ServiceErrorCode.TASK_NOT_RESUMABLE
        )

    def test_control_unknown_task_is_not_found(self):
        service, _ = _service()
        self.assertEqual(
            service.cancel_task("nope").error.code,
            ServiceErrorCode.TASK_NOT_FOUND,
        )


# =====================================================================
# Task-lifecycle transition table
# =====================================================================
class TransitionTableTests(unittest.TestCase):
    def test_pause_running(self):
        self.assertEqual(
            next_task_state(TaskState.RUNNING, TaskAction.PAUSE),
            TaskState.PAUSED,
        )

    def test_resume_paused(self):
        self.assertEqual(
            next_task_state(TaskState.PAUSED, TaskAction.RESUME),
            TaskState.RUNNING,
        )

    def test_cancel_running_and_paused(self):
        self.assertEqual(
            next_task_state(TaskState.RUNNING, TaskAction.CANCEL),
            TaskState.CANCELLED,
        )
        self.assertEqual(
            next_task_state(TaskState.PAUSED, TaskAction.CANCEL),
            TaskState.CANCELLED,
        )

    def test_cancel_terminal_withdraws(self):
        self.assertEqual(
            next_task_state(TaskState.COMPLETED, TaskAction.CANCEL),
            TaskState.CANCELLED,
        )
        self.assertEqual(
            next_task_state(TaskState.FAILED, TaskAction.CANCEL),
            TaskState.CANCELLED,
        )

    def test_illegal_transitions_raise(self):
        for state, action in (
            (TaskState.COMPLETED, TaskAction.PAUSE),
            (TaskState.PAUSED, TaskAction.PAUSE),
            (TaskState.RUNNING, TaskAction.RESUME),
            (TaskState.CANCELLED, TaskAction.CANCEL),
        ):
            with self.assertRaises(InvalidTaskTransitionException):
                next_task_state(state, action)


# =====================================================================
# Session lifecycle (SessionManager)
# =====================================================================
class SessionManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = SessionManager()

    def test_create_opens_active_session(self):
        session = self.manager.create("e1", "task-1")
        self.assertIsInstance(session, SessionInfo)
        self.assertEqual(session.status, SessionStatus.ACTIVE)
        self.assertTrue(session.active)

    def test_load_returns_session(self):
        created = self.manager.create("e1", "task-1")
        self.assertEqual(
            self.manager.load(created.session_id).session_id,
            created.session_id,
        )

    def test_load_missing_raises(self):
        with self.assertRaises(SessionNotFoundException):
            self.manager.load("nope")

    def test_close_transitions_to_closed(self):
        created = self.manager.create("e1", "task-1")
        closed = self.manager.close(created.session_id)
        self.assertEqual(closed.status, SessionStatus.CLOSED)
        self.assertFalse(closed.active)
        self.assertIsNotNone(closed.closed_at_sequence)

    def test_close_missing_raises(self):
        with self.assertRaises(SessionNotFoundException):
            self.manager.close("nope")

    def test_list_and_active(self):
        a = self.manager.create("e1", "t1")
        self.manager.create("e2", "t2")
        self.manager.close(a.session_id)
        self.assertEqual(len(self.manager.list()), 2)
        self.assertEqual(len(self.manager.active()), 1)


# =====================================================================
# Validation (RequestValidator)
# =====================================================================
class RequestValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = RequestValidator()

    def test_valid_request_passes(self):
        self.assertIsNone(self.validator.validate(_request()))

    def test_duplicate_step_ids_rejected(self):
        request = TaskSubmissionRequest(
            request_id="r1",
            employee=EmployeeProfile(employee_id="e1", name="Ada"),
            task_id="b1",
            task="do it",
            workflow_steps=[
                WorkflowStep(step_id="s1", capability_name="demo"),
                WorkflowStep(step_id="s1", capability_name="demo"),
            ],
        )
        with self.assertRaises(ValidationException) as ctx:
            self.validator.validate(request)
        self.assertTrue(ctx.exception.issues)

    def test_empty_capability_rejected(self):
        request = TaskSubmissionRequest(
            request_id="r1",
            employee=EmployeeProfile(employee_id="e1", name="Ada"),
            task_id="b1",
            task="do it",
            workflow_steps=[WorkflowStep(step_id="s1", capability_name="  ")],
        )
        with self.assertRaises(ValidationException):
            self.validator.validate(request)

    def test_wrong_type_rejected(self):
        with self.assertRaises(ValidationException):
            self.validator.validate({"not": "a request"})

    def test_service_returns_validation_error_response(self):
        service, _ = _service()
        request = TaskSubmissionRequest(
            request_id="r1",
            employee=EmployeeProfile(employee_id="e1", name="Ada"),
            task_id="b1",
            task="do it",
            workflow_steps=[
                WorkflowStep(step_id="dup", capability_name="demo"),
                WorkflowStep(step_id="dup", capability_name="demo"),
            ],
        )
        response = service.submit_task(request)
        self.assertFalse(response.accepted)
        self.assertEqual(
            response.error.code, ServiceErrorCode.VALIDATION_ERROR
        )


# =====================================================================
# Response contracts (ResponseBuilder)
# =====================================================================
class ResponseBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = ResponseBuilder()

    def test_success_is_accepted(self):
        response = self.builder.success(
            "r1", "task-1", TaskState.COMPLETED, "sess-1"
        )
        self.assertTrue(response.accepted)
        self.assertEqual(response.state, TaskState.COMPLETED)

    def test_failure_carries_error(self):
        error = ServiceError(code=ServiceErrorCode.VALIDATION_ERROR)
        response = self.builder.failure("r1", error)
        self.assertFalse(response.accepted)
        self.assertIs(response.error, error)

    def test_status_flavors(self):
        cases = [
            (self.builder.running("t"), TaskState.RUNNING, False),
            (self.builder.completed("t"), TaskState.COMPLETED, True),
            (self.builder.failed("t"), TaskState.FAILED, False),
            (self.builder.cancelled("t"), TaskState.CANCELLED, False),
            (self.builder.paused("t"), TaskState.PAUSED, False),
        ]
        for response, state, success in cases:
            self.assertEqual(response.state, state)
            self.assertEqual(response.success, success)

    def test_not_found_and_errored(self):
        error = ServiceError(code=ServiceErrorCode.TASK_NOT_FOUND)
        nf = self.builder.not_found("t", error)
        self.assertIsNone(nf.state)
        self.assertIs(nf.error, error)
        er = self.builder.errored("t", TaskState.COMPLETED, "s", error)
        self.assertEqual(er.state, TaskState.COMPLETED)
        self.assertFalse(er.success)


# =====================================================================
# Idempotency (IdempotencyManager + service)
# =====================================================================
class IdempotencyTests(unittest.TestCase):
    def test_same_request_same_key_replays_same_task(self):
        service, workflow = _service()
        request = _request(idempotency_key="k1")
        first = service.submit_task(request)
        second = service.submit_task(request)
        self.assertEqual(first.task_id, second.task_id)
        self.assertTrue(second.idempotent)
        self.assertFalse(first.idempotent)
        self.assertEqual(len(workflow.calls), 1)  # executed only once

    def test_same_key_different_request_conflicts(self):
        service, _ = _service()
        service.submit_task(_request(task_id="b1", idempotency_key="k1"))
        conflict = service.submit_task(
            _request(request_id="r2", task_id="b2", idempotency_key="k1")
        )
        self.assertFalse(conflict.accepted)
        self.assertEqual(
            conflict.error.code, ServiceErrorCode.IDEMPOTENCY_CONFLICT
        )

    def test_no_key_never_deduplicates(self):
        service, workflow = _service()
        service.submit_task(_request(request_id="r1", task_id="b1"))
        service.submit_task(_request(request_id="r2", task_id="b2"))
        self.assertEqual(len(workflow.calls), 2)

    def test_manager_register_exists_resolve(self):
        manager = IdempotencyManager()
        response = TaskSubmissionResponse(
            request_id="r1", task_id="task-1", accepted=True
        )
        record = manager.register("k1", "r1", "task-1", "fp", response)
        self.assertIsInstance(record, IdempotencyRecord)
        self.assertTrue(manager.exists("k1"))
        self.assertFalse(manager.exists("other"))
        self.assertIs(manager.resolve("k1").response, response)
        self.assertIsNone(manager.resolve("other"))

    def test_fingerprint_is_deterministic(self):
        manager = IdempotencyManager()
        self.assertEqual(
            manager.fingerprint(_request()), manager.fingerprint(_request())
        )
        self.assertNotEqual(
            manager.fingerprint(_request(task_id="a")),
            manager.fingerprint(_request(task_id="b")),
        )


# =====================================================================
# Health / readiness (HealthManager + service)
# =====================================================================
class HealthTests(unittest.TestCase):
    def test_all_up_is_healthy(self):
        manager = HealthManager({name: True for name in HEALTH_COMPONENTS})
        report = manager.health()
        self.assertIsInstance(report, HealthStatus)
        self.assertEqual(report.state, HealthState.HEALTHY)
        self.assertTrue(report.ready)
        self.assertEqual(len(report.components), len(HEALTH_COMPONENTS))

    def test_some_down_is_degraded(self):
        components = {name: True for name in HEALTH_COMPONENTS}
        components["memory"] = False
        report = HealthManager(components).health()
        self.assertEqual(report.state, HealthState.DEGRADED)
        self.assertFalse(report.ready)
        self.assertEqual(report.components["memory"], "UNHEALTHY")

    def test_all_down_is_unhealthy(self):
        report = HealthManager(
            {name: False for name in HEALTH_COMPONENTS}
        ).health()
        self.assertEqual(report.state, HealthState.UNHEALTHY)

    def test_missing_component_treated_unavailable(self):
        report = HealthManager({"planning": True}).health()
        self.assertEqual(report.components["runtime"], "UNHEALTHY")

    def test_reports_all_required_subsystems(self):
        report = HealthManager(_healthy_components()).health()
        for name in (
            "planning",
            "runtime",
            "ai_employee",
            "memory",
            "scheduler",
            "recovery",
            "persistence",
        ):
            self.assertIn(name, report.components)

    def test_readiness_true_only_when_healthy(self):
        self.assertTrue(
            HealthManager(_healthy_components()).readiness().ready
        )
        degraded = {name: True for name in HEALTH_COMPONENTS}
        degraded["recovery"] = False
        self.assertFalse(HealthManager(degraded).readiness().ready)

    def test_service_exposes_health_and_readiness(self):
        service, _ = _service()
        self.assertEqual(service.health().state, HealthState.HEALTHY)
        self.assertTrue(service.readiness().ready)


# =====================================================================
# Error mapping (ErrorMapper)
# =====================================================================
class ErrorMapperTests(unittest.TestCase):
    def setUp(self):
        self.mapper = ErrorMapper()

    def test_validation_exception(self):
        error = self.mapper.map(ValidationException("bad", issues=["x"]))
        self.assertEqual(error.code, ServiceErrorCode.VALIDATION_ERROR)
        self.assertEqual(error.error_metadata["issues"], ["x"])

    def test_invalid_transition_by_action(self):
        for action, code in (
            (TaskAction.PAUSE, ServiceErrorCode.TASK_NOT_PAUSABLE),
            (TaskAction.RESUME, ServiceErrorCode.TASK_NOT_RESUMABLE),
            (TaskAction.CANCEL, ServiceErrorCode.TASK_NOT_CANCELLABLE),
        ):
            exc = InvalidTaskTransitionException(
                state=TaskState.COMPLETED, action=action
            )
            self.assertEqual(self.mapper.map(exc).code, code)

    def test_task_and_session_not_found(self):
        self.assertEqual(
            self.mapper.map(TaskNotFoundException("t")).code,
            ServiceErrorCode.TASK_NOT_FOUND,
        )
        self.assertEqual(
            self.mapper.map(SessionNotFoundException("s")).code,
            ServiceErrorCode.SESSION_NOT_FOUND,
        )

    def test_pydantic_validation_error(self):
        try:
            TaskSubmissionRequest(request_id="", employee=None, task_id="", task="")
        except ValidationError as exc:
            error = self.mapper.map(exc)
            self.assertEqual(error.code, ServiceErrorCode.VALIDATION_ERROR)

    def test_frozen_collaborator_errors(self):
        self.assertEqual(
            self.mapper.map(CoordinationTaskNotFoundError("x")).code,
            ServiceErrorCode.TASK_NOT_FOUND,
        )
        self.assertEqual(
            self.mapper.map(CoordinationAgentNotFoundError("x")).code,
            ServiceErrorCode.AGENT_NOT_FOUND,
        )
        self.assertEqual(
            self.mapper.map(ScheduleNotFoundError("x")).code,
            ServiceErrorCode.SCHEDULE_NOT_FOUND,
        )
        self.assertEqual(
            self.mapper.map(MissingWorkflowError("x")).code,
            ServiceErrorCode.PERSISTENCE_ERROR,
        )

    def test_unknown_exception_is_internal(self):
        error = self.mapper.map(RuntimeError("boom"))
        self.assertEqual(error.code, ServiceErrorCode.INTERNAL_ERROR)
        self.assertEqual(error.error_metadata["type"], "RuntimeError")


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def test_submission_request_is_frozen(self):
        with self.assertRaises(ValidationError):
            _request().task = "changed"

    def test_submission_response_is_frozen(self):
        with self.assertRaises(ValidationError):
            TaskSubmissionResponse(accepted=True).accepted = False

    def test_status_response_is_frozen(self):
        with self.assertRaises(ValidationError):
            TaskStatusResponse(state=TaskState.RUNNING).success = True

    def test_session_info_is_frozen(self):
        with self.assertRaises(ValidationError):
            SessionInfo(session_id="s").active = False

    def test_health_status_is_frozen(self):
        with self.assertRaises(ValidationError):
            HealthStatus(state=HealthState.HEALTHY).ready = False

    def test_service_error_is_frozen(self):
        with self.assertRaises(ValidationError):
            ServiceError(code=ServiceErrorCode.INTERNAL_ERROR).message = "x"

    def test_idempotency_record_is_frozen(self):
        record = IdempotencyRecord(
            key="k",
            response=TaskSubmissionResponse(accepted=True),
        )
        with self.assertRaises(ValidationError):
            record.key = "other"

    def test_request_requires_non_empty_fields(self):
        with self.assertRaises(ValidationError):
            TaskSubmissionRequest(
                request_id="r1",
                employee=EmployeeProfile(employee_id="e1", name="Ada"),
                task_id="b1",
                task="",
            )


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_error_mapper,
            get_health_manager,
            get_idempotency_manager,
            get_request_validator,
            get_response_builder,
            get_service_session_manager,
        )

        self.assertIsInstance(get_service_session_manager(), SessionManager)
        self.assertIsInstance(get_request_validator(), RequestValidator)
        self.assertIsInstance(get_response_builder(), ResponseBuilder)
        self.assertIsInstance(get_idempotency_manager(), IdempotencyManager)
        self.assertIsInstance(get_health_manager(), HealthManager)
        self.assertIsInstance(get_error_mapper(), ErrorMapper)

    def test_service_provider_wires_collaborators(self):
        from app.core.dependencies import get_ai_employee_service

        service = get_ai_employee_service()
        self.assertIsInstance(service, AIEmployeeService)
        self.assertIsInstance(service.ai_employee, AIEmployee)
        self.assertIsInstance(service.session_manager, SessionManager)
        self.assertIsInstance(service.validator, RequestValidator)
        self.assertIsInstance(service.response_builder, ResponseBuilder)
        self.assertIsInstance(
            service.idempotency_manager, IdempotencyManager
        )
        self.assertIsInstance(service.health_manager, HealthManager)
        self.assertIsInstance(service.error_mapper, ErrorMapper)

    def test_service_provider_uses_injected(self):
        from app.core.dependencies import get_ai_employee_service

        validator = RequestValidator()
        service = get_ai_employee_service(validator=validator)
        self.assertIs(service.validator, validator)

    def test_default_health_is_healthy(self):
        from app.core.dependencies import get_health_manager

        self.assertEqual(
            get_health_manager().health().state, HealthState.HEALTHY
        )

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            AIEmployeeServiceDep,
            ErrorMapperDep,
            HealthManagerDep,
            IdempotencyManagerDep,
            RequestValidatorDep,
            ResponseBuilderDep,
            ServiceSessionManagerDep,
        )

        for dep in (
            ServiceSessionManagerDep,
            RequestValidatorDep,
            ResponseBuilderDep,
            IdempotencyManagerDep,
            HealthManagerDep,
            ErrorMapperDep,
            AIEmployeeServiceDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: prior sprints frozen; no forbidden imports
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_MODULES = {
        "workflow_coordinator",
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
        "repository",
        "fastapi",
        "starlette",
        "sqlalchemy",
        "database",
        "threading",
        "asyncio",
        "socket",
        "requests",
        "httpx",
        "anthropic",
        "openai",
    }

    def test_frozen_169_coordinator_unchanged(self):
        from app.core.dependencies import get_agent_coordinator
        import app.services.ai_employee.coordination as coordination

        self.assertIsInstance(
            get_agent_coordinator(), coordination.AgentCoordinator
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_service_never_holds_workflow_coordinator(self):
        service, _ = _service()
        self.assertEqual(
            set(vars(service)),
            {
                "ai_employee",
                "session_manager",
                "validator",
                "response_builder",
                "idempotency_manager",
                "health_manager",
                "error_mapper",
                "_tasks",
                "_sequence",
            },
        )

    def test_service_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.service as pkg

        package_dir = os.path.dirname(pkg.__file__)
        offenders = []
        for filename in os.listdir(package_dir):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(package_dir, filename)
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                elif isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                for name in names:
                    tail = name.rsplit(".", 1)[-1]
                    if tail in self._FORBIDDEN_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
