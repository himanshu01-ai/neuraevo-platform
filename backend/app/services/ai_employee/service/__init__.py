"""AI Employee Service Layer package (Sprint 16.10 — the stable public entry point).

Exposes the AI Employee through a single, stable, provider-independent Service Layer
that applications use to submit and control tasks. The Service Layer *coordinates
external requests* and always delegates the running to the frozen Sprint 16.1
:class:`AIEmployee` — it executes no workflow or capability itself, never calls the
Workflow Coordinator, and never surfaces a raw exception. There is no HTTP, REST,
GraphQL, gRPC, WebSocket, auth, LLM provider, or database here. It follows the flow
``AIEmployeeService -> {SessionManager, RequestValidator, ResponseBuilder,
IdempotencyManager, HealthManager, ErrorMapper}`` over the :class:`AIEmployee`:

* the immutable DTOs :class:`TaskSubmissionRequest`, :class:`TaskSubmissionResponse`,
  :class:`TaskStatusResponse`, :class:`SessionInfo`, :class:`HealthStatus`,
  :class:`ServiceError`, and :class:`IdempotencyRecord`, plus the :class:`TaskState`,
  :class:`TaskAction`, :class:`SessionStatus`, :class:`HealthState`, and
  :class:`ServiceErrorCode` enums and the :class:`ServiceException` family;
* the :class:`SessionManager`, :class:`RequestValidator`, :class:`ResponseBuilder`,
  :class:`IdempotencyManager`, :class:`HealthManager`, and :class:`ErrorMapper`
  collaborators; and
* the :class:`AIEmployeeService` entry point.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.9, and it imports no Workflow Coordinator, capability module, repository,
LLM provider, database, or web/transport facility.
"""

from app.services.ai_employee.service.error_mapper import ErrorMapper
from app.services.ai_employee.service.health import (
    HEALTH_COMPONENTS,
    HealthManager,
)
from app.services.ai_employee.service.idempotency import IdempotencyManager
from app.services.ai_employee.service.models import (
    HealthState,
    HealthStatus,
    IdempotencyRecord,
    InvalidTaskTransitionException,
    ServiceError,
    ServiceErrorCode,
    ServiceException,
    SessionInfo,
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
from app.services.ai_employee.service.response_builder import ResponseBuilder
from app.services.ai_employee.service.service import AIEmployeeService
from app.services.ai_employee.service.session_manager import SessionManager
from app.services.ai_employee.service.validator import RequestValidator

__all__ = [
    # DTOs
    "TaskSubmissionRequest",
    "TaskSubmissionResponse",
    "TaskStatusResponse",
    "SessionInfo",
    "HealthStatus",
    "ServiceError",
    "IdempotencyRecord",
    # enums
    "TaskState",
    "TaskAction",
    "SessionStatus",
    "HealthState",
    "ServiceErrorCode",
    # lifecycle helper
    "next_task_state",
    # exceptions
    "ServiceException",
    "ValidationException",
    "TaskNotFoundException",
    "SessionNotFoundException",
    "InvalidTaskTransitionException",
    # collaborators
    "SessionManager",
    "RequestValidator",
    "ResponseBuilder",
    "IdempotencyManager",
    "HealthManager",
    "HEALTH_COMPONENTS",
    "ErrorMapper",
    # service
    "AIEmployeeService",
]
