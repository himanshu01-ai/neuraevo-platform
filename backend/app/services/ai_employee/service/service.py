"""AI Employee Service (Sprint 16.10 — the stable public entry point).

Defines :class:`AIEmployeeService`, the single, stable public entry point through
which applications submit and control AI Employee tasks. It coordinates external
requests over its injected collaborators — the :class:`SessionManager`,
:class:`RequestValidator`, :class:`ResponseBuilder`, :class:`IdempotencyManager`,
:class:`HealthManager`, and :class:`ErrorMapper` — and *always delegates the running
to the frozen Sprint 16.1* :class:`AIEmployee`:

    submit_task   (validate -> dedupe -> open session -> delegate to AIEmployee)
    get_task / list_tasks   (read stable task status)
    cancel_task / pause_task / resume_task   (deterministic lifecycle control)
    health / readiness   (provider-independent platform health)

It never executes a workflow or capability itself, never calls the Workflow
Coordinator, and never surfaces a raw exception: every failure is converted to a
stable :class:`ServiceError` carried inside a response DTO. Constructor injection
only; its only state is the in-memory task registry and a deterministic sequence
counter — no static, singleton, or service-locator state. Strictly additive to
Sprints 1.x–16.9, whose modules are left untouched.
"""

from typing import Dict, List, Optional

from app.services.ai_employee.ai_employee import AIEmployee
from app.services.ai_employee.models import (
    EmployeeSessionStatus,
    TaskDelegation,
)
from app.services.ai_employee.service.error_mapper import ErrorMapper
from app.services.ai_employee.service.health import HealthManager
from app.services.ai_employee.service.idempotency import IdempotencyManager
from app.services.ai_employee.service.models import (
    HealthStatus,
    ServiceError,
    ServiceErrorCode,
    TaskAction,
    TaskNotFoundException,
    TaskState,
    TaskStatusResponse,
    TaskSubmissionRequest,
    TaskSubmissionResponse,
    next_task_state,
)
from app.services.ai_employee.service.response_builder import ResponseBuilder
from app.services.ai_employee.service.session_manager import SessionManager
from app.services.ai_employee.service.validator import RequestValidator


class _TaskRecord:
    """Mutable, in-memory record of one submitted task (internal, never exposed).

    Holds the service task id, the caller's business task id, the current
    :class:`TaskState`, the session id, the originating request, the frozen
    :class:`EmployeeExecutionResult` from the delegated run, and the idempotency key.
    Only ``state`` changes (via the lifecycle transitions); nothing here executes.
    """

    __slots__ = (
        "task_id",
        "business_task_id",
        "state",
        "session_id",
        "employee_result",
        "idempotency_key",
    )

    def __init__(
        self,
        task_id: str,
        business_task_id: str,
        state: TaskState,
        session_id: str,
        employee_result,
        idempotency_key: Optional[str],
    ) -> None:
        self.task_id = task_id
        self.business_task_id = business_task_id
        self.state = state
        self.session_id = session_id
        self.employee_result = employee_result
        self.idempotency_key = idempotency_key


class AIEmployeeService:
    """The stable public service coordinating AI Employee task submission and control.

    Constructed with an injected :class:`AIEmployee`, :class:`SessionManager`,
    :class:`RequestValidator`, :class:`ResponseBuilder`, :class:`IdempotencyManager`,
    :class:`HealthManager`, and :class:`ErrorMapper` (constructor injection; it
    instantiates none of them). It validates and deduplicates submissions, opens a
    session, delegates the run to the :class:`AIEmployee`, records the task, exposes
    stable status/health, and applies deterministic lifecycle controls — never
    executing a workflow or capability itself and never surfacing a raw exception. Its
    only state is the task registry and a deterministic sequence counter.
    """

    def __init__(
        self,
        ai_employee: AIEmployee,
        session_manager: SessionManager,
        validator: RequestValidator,
        response_builder: ResponseBuilder,
        idempotency_manager: IdempotencyManager,
        health_manager: HealthManager,
        error_mapper: ErrorMapper,
    ) -> None:
        self.ai_employee = ai_employee
        self.session_manager = session_manager
        self.validator = validator
        self.response_builder = response_builder
        self.idempotency_manager = idempotency_manager
        self.health_manager = health_manager
        self.error_mapper = error_mapper
        self._tasks: Dict[str, _TaskRecord] = {}
        self._sequence = 0

    # --- submission ------------------------------------------------------
    def submit_task(
        self, request: TaskSubmissionRequest
    ) -> TaskSubmissionResponse:
        """Validate, deduplicate, and delegate ``request`` to the :class:`AIEmployee`.

        Validates the request; on an idempotency-key hit replays the original
        response (or reports a conflict when the same key carries a different
        request); otherwise opens a session, delegates the run to the
        :class:`AIEmployee`, records the task in its terminal state, and returns an
        accepted response. Any failure is returned as a rejected response carrying a
        stable :class:`ServiceError` — never a raw exception. The service delegates
        the running; it executes nothing itself.
        """
        request_id = getattr(request, "request_id", "")
        try:
            self.validator.validate(request)
        except Exception as exc:  # noqa: BLE001 - mapped, never re-raised
            return self.response_builder.failure(
                request_id, self.error_mapper.map(exc)
            )

        key = request.idempotency_key
        fingerprint = self.idempotency_manager.fingerprint(request)
        if key and self.idempotency_manager.exists(key):
            record = self.idempotency_manager.resolve(key)
            if record is not None and record.fingerprint == fingerprint:
                return record.response.model_copy(update={"idempotent": True})
            return self.response_builder.failure(
                request_id,
                ServiceError(
                    code=ServiceErrorCode.IDEMPOTENCY_CONFLICT,
                    message=f"idempotency key {key!r} reused with a "
                    "different request",
                    retryable=False,
                ),
            )

        task_id = f"task-{self._next()}"
        session = self.session_manager.create(
            request.employee.employee_id, task_id
        )
        try:
            result = self.ai_employee.delegate(
                request.employee,
                self._to_delegation(request),
                list(request.workflow_steps),
                request.initial_inputs or None,
            )
        except Exception as exc:  # noqa: BLE001 - mapped, never re-raised
            self.session_manager.close(session.session_id)
            return self.response_builder.failure(
                request_id,
                ServiceError(
                    code=ServiceErrorCode.DELEGATION_FAILED,
                    message=str(exc) or exc.__class__.__name__,
                    retryable=True,
                    error_metadata={"type": exc.__class__.__name__},
                ),
                task_id=task_id,
            )

        state = (
            TaskState.COMPLETED
            if result.status == EmployeeSessionStatus.COMPLETED
            else TaskState.FAILED
        )
        self._tasks[task_id] = _TaskRecord(
            task_id=task_id,
            business_task_id=request.task_id,
            state=state,
            session_id=session.session_id,
            employee_result=result,
            idempotency_key=key,
        )
        response = self.response_builder.success(
            request_id, task_id, state, session.session_id
        )
        if key:
            self.idempotency_manager.register(
                key, request_id, task_id, fingerprint, response
            )
        return response

    # --- reads -----------------------------------------------------------
    def get_task(self, task_id: str) -> TaskStatusResponse:
        """Return the stable :class:`TaskStatusResponse` for ``task_id``.

        Returns a not-found status carrying a :class:`ServiceError` when the task is
        unknown. Read-only — it runs nothing.
        """
        record = self._tasks.get(task_id)
        if record is None:
            return self.response_builder.not_found(
                task_id,
                self.error_mapper.map(TaskNotFoundException(task_id)),
            )
        return self._status_for(record)

    def list_tasks(self) -> List[TaskStatusResponse]:
        """Return the status of every tracked task in submission order."""
        return [self._status_for(record) for record in self._tasks.values()]

    # --- lifecycle control ----------------------------------------------
    def cancel_task(self, task_id: str) -> TaskStatusResponse:
        """Withdraw ``task_id`` (transition to ``CANCELLED``) and close its session."""
        return self._control(task_id, TaskAction.CANCEL)

    def pause_task(self, task_id: str) -> TaskStatusResponse:
        """Pause ``task_id`` (``RUNNING`` -> ``PAUSED``); illegal otherwise."""
        return self._control(task_id, TaskAction.PAUSE)

    def resume_task(self, task_id: str) -> TaskStatusResponse:
        """Resume ``task_id`` (``PAUSED`` -> ``RUNNING``); illegal otherwise."""
        return self._control(task_id, TaskAction.RESUME)

    # --- health ----------------------------------------------------------
    def health(self) -> HealthStatus:
        """Return the platform's provider-independent :class:`HealthStatus`."""
        return self.health_manager.health()

    def readiness(self) -> HealthStatus:
        """Return the platform's provider-independent readiness :class:`HealthStatus`."""
        return self.health_manager.readiness()

    # --- helpers ---------------------------------------------------------
    def _control(
        self, task_id: str, action: TaskAction
    ) -> TaskStatusResponse:
        """Apply a lifecycle ``action`` to ``task_id`` and return its status.

        Returns a not-found status for an unknown task and an errored status (state
        unchanged) for an illegal transition; otherwise transitions the task, closes
        the session on cancel, and returns the new status. Deterministic; it runs
        nothing.
        """
        record = self._tasks.get(task_id)
        if record is None:
            return self.response_builder.not_found(
                task_id,
                self.error_mapper.map(TaskNotFoundException(task_id)),
            )
        try:
            new_state = next_task_state(record.state, action)
        except Exception as exc:  # noqa: BLE001 - mapped, never re-raised
            return self.response_builder.errored(
                task_id,
                record.state,
                record.session_id,
                self.error_mapper.map(exc),
            )
        previous = record.state
        record.state = new_state
        if action == TaskAction.CANCEL:
            self.session_manager.close(record.session_id)
        return self._status_for(
            record, response_metadata={"previous_state": previous.value}
        )

    def _status_for(
        self,
        record: _TaskRecord,
        response_metadata: Optional[Dict[str, str]] = None,
    ) -> TaskStatusResponse:
        """Build the :class:`TaskStatusResponse` for ``record`` in its current state."""
        return self.response_builder.status(
            record.task_id,
            record.state,
            record.session_id,
            self._summary(record),
            response_metadata,
        )

    @staticmethod
    def _summary(record: _TaskRecord) -> Dict[str, object]:
        """Return a provider-independent summary of the delegated outcome."""
        summary: Dict[str, object] = {
            "business_task_id": record.business_task_id
        }
        result = record.employee_result
        if result is not None:
            # ``result_metadata`` already holds provider-independent descriptors
            # (workflow status, planned step count) produced by the AIEmployee.
            summary.update(dict(result.result_metadata))
        return summary

    @staticmethod
    def _to_delegation(request: TaskSubmissionRequest) -> TaskDelegation:
        """Build the Sprint 16.1 :class:`TaskDelegation` for ``request``."""
        return TaskDelegation(
            task_id=request.task_id,
            task=request.task,
            constraints=list(request.constraints),
            priority=request.priority,
            delegation_metadata=dict(request.request_metadata),
        )

    def _next(self) -> int:
        """Return the next deterministic sequence ordinal."""
        self._sequence += 1
        return self._sequence
