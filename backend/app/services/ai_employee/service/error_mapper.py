"""Error mapper (Sprint 16.10 — convert exceptions into stable service errors).

Defines :class:`ErrorMapper`, which converts any exception raised inside the Service
Layer — its own :class:`ServiceException` family, a Pydantic ``ValidationError``, or
a deterministic error from a frozen collaborator (Agent Coordination, Scheduler,
Persistence) — into a stable, provider-independent :class:`ServiceError` with a
deterministic :class:`ServiceErrorCode`. Anything unrecognised maps to
``INTERNAL_ERROR``. No raw exception ever crosses the service boundary.

It is deterministic and stateless: it maps only and decides, delegates, and executes
nothing. It never touches the Workflow Coordinator, a capability, a repository, a
database, an LLM provider, a thread, or the network. Strictly additive to Sprints
1.x–16.9, whose modules are left untouched.
"""

from pydantic import ValidationError

from app.services.ai_employee.coordination.models import (
    AgentNotFoundError as CoordinationAgentNotFoundError,
)
from app.services.ai_employee.coordination.models import (
    TaskNotFoundError as CoordinationTaskNotFoundError,
)
from app.services.ai_employee.persistence.models import (
    MissingVersionError,
    MissingWorkflowError,
)
from app.services.ai_employee.scheduler.models import ScheduleNotFoundError
from app.services.ai_employee.service.models import (
    InvalidTaskTransitionException,
    ServiceError,
    ServiceErrorCode,
    SessionNotFoundException,
    TaskAction,
    TaskNotFoundException,
    ValidationException,
)

# The precise service error code per attempted control action for an illegal
# task-lifecycle transition.
_TRANSITION_CODES = {
    TaskAction.PAUSE: ServiceErrorCode.TASK_NOT_PAUSABLE,
    TaskAction.RESUME: ServiceErrorCode.TASK_NOT_RESUMABLE,
    TaskAction.CANCEL: ServiceErrorCode.TASK_NOT_CANCELLABLE,
}


class ErrorMapper:
    """Maps any exception to a stable :class:`ServiceError` (deterministic).

    ``map`` recognises the Service Layer's own exceptions, Pydantic validation
    errors, and the frozen collaborators' deterministic not-found errors, assigning
    each a stable :class:`ServiceErrorCode`; anything else becomes ``INTERNAL_ERROR``.
    Stateless; it maps only and never surfaces a raw exception.
    """

    def map(self, exc: Exception) -> ServiceError:
        """Return the stable :class:`ServiceError` for ``exc``."""
        if isinstance(exc, ValidationException):
            return ServiceError(
                code=ServiceErrorCode.VALIDATION_ERROR,
                message=str(exc),
                retryable=False,
                error_metadata={"issues": list(exc.issues)},
            )
        if isinstance(exc, InvalidTaskTransitionException):
            return ServiceError(
                code=_TRANSITION_CODES.get(
                    exc.action, ServiceErrorCode.INTERNAL_ERROR
                ),
                message=str(exc),
                retryable=False,
                error_metadata={
                    "state": exc.state.value,
                    "action": exc.action.value,
                },
            )
        if isinstance(exc, TaskNotFoundException):
            return ServiceError(
                code=ServiceErrorCode.TASK_NOT_FOUND, message=str(exc)
            )
        if isinstance(exc, SessionNotFoundException):
            return ServiceError(
                code=ServiceErrorCode.SESSION_NOT_FOUND, message=str(exc)
            )
        if isinstance(exc, ValidationError):
            return ServiceError(
                code=ServiceErrorCode.VALIDATION_ERROR,
                message="request failed schema validation",
                retryable=False,
                error_metadata={"errors": exc.error_count()},
            )
        if isinstance(exc, CoordinationTaskNotFoundError):
            return ServiceError(
                code=ServiceErrorCode.TASK_NOT_FOUND, message=str(exc)
            )
        if isinstance(exc, CoordinationAgentNotFoundError):
            return ServiceError(
                code=ServiceErrorCode.AGENT_NOT_FOUND, message=str(exc)
            )
        if isinstance(exc, ScheduleNotFoundError):
            return ServiceError(
                code=ServiceErrorCode.SCHEDULE_NOT_FOUND, message=str(exc)
            )
        if isinstance(exc, (MissingWorkflowError, MissingVersionError)):
            return ServiceError(
                code=ServiceErrorCode.PERSISTENCE_ERROR, message=str(exc)
            )
        return ServiceError(
            code=ServiceErrorCode.INTERNAL_ERROR,
            message=str(exc) or exc.__class__.__name__,
            retryable=False,
            error_metadata={"type": exc.__class__.__name__},
        )
