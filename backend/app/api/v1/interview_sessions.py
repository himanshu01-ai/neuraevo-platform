"""Interview session API endpoints (nested under an employee)."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUserDep, InterviewSessionServiceDep
from app.schemas.interview_session import (
    InterviewSessionCreate,
    InterviewSessionResponse,
    InterviewSessionUpdate,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)
from app.services.interview_session_service import (
    InterviewSessionError,
    InterviewSessionNotFoundError,
    InterviewSessionStateError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/sessions", tags=["Interview Sessions"]
)

_OWNERSHIP_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee or session does not exist."
    },
}

_UPDATE_RESPONSES = {
    **_OWNERSHIP_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "description": "Invalid interview-session status transition."
    },
}

# Maps domain exceptions to the (status code, detail) used in HTTP responses.
_DOMAIN_HTTP_MAP: list[tuple[type[Exception], int, str]] = [
    (EmployeeNotFoundError, status.HTTP_404_NOT_FOUND, "Employee not found."),
    (
        EmployeeAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this employee.",
    ),
    (
        InterviewSessionNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Interview session not found.",
    ),
    (
        InterviewSessionStateError,
        status.HTTP_409_CONFLICT,
        "Invalid interview-session status transition.",
    ),
]


def _to_http_exception(
    exc: EmployeeError | InterviewSessionError,
) -> HTTPException:
    """Translate an ownership/lookup/state domain error into an HTTPException."""
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            # State errors carry a specific message; surface it when present.
            detail_msg = str(exc) if isinstance(exc, InterviewSessionStateError) else detail
            return HTTPException(status_code=code, detail=detail_msg)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an interview session for the authenticated user's employee",
    responses=_OWNERSHIP_RESPONSES,
)
def create_session(
    employee_id: uuid.UUID,
    data: InterviewSessionCreate,
    current_user: CurrentUserDep,
    service: InterviewSessionServiceDep,
) -> InterviewSessionResponse:
    """Create an interview session.

    The employee must belong to the authenticated user. ``status`` defaults to
    ``created``; ``started_at`` is auto-generated and ``completed_at`` starts
    null.
    """
    try:
        interview_session = service.create_session(
            current_user, employee_id, data
        )
    except (EmployeeError, InterviewSessionError) as exc:
        raise _to_http_exception(exc)
    return InterviewSessionResponse.model_validate(interview_session)


@router.get(
    "",
    response_model=List[InterviewSessionResponse],
    summary="List interview sessions for the employee",
    responses=_OWNERSHIP_RESPONSES,
)
def list_sessions(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewSessionServiceDep,
) -> List[InterviewSessionResponse]:
    """List the employee's interview sessions, ordered by started_at."""
    try:
        sessions = service.list_sessions(current_user, employee_id)
    except (EmployeeError, InterviewSessionError) as exc:
        raise _to_http_exception(exc)
    return [InterviewSessionResponse.model_validate(s) for s in sessions]


@router.get(
    "/{session_id}",
    response_model=InterviewSessionResponse,
    summary="Get a single interview session",
    responses=_OWNERSHIP_RESPONSES,
)
def get_session(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewSessionServiceDep,
) -> InterviewSessionResponse:
    """Return a single session by id, scoped to the employee.

    Returns ``404`` if the session does not exist or belongs to a different
    employee. Invalid path UUIDs yield ``422``.
    """
    try:
        interview_session = service.get_session(
            current_user, employee_id, session_id
        )
    except (EmployeeError, InterviewSessionError) as exc:
        raise _to_http_exception(exc)
    return InterviewSessionResponse.model_validate(interview_session)


@router.patch(
    "/{session_id}",
    response_model=InterviewSessionResponse,
    summary="Update an interview session",
    responses=_UPDATE_RESPONSES,
)
def update_session(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    data: InterviewSessionUpdate,
    current_user: CurrentUserDep,
    service: InterviewSessionServiceDep,
) -> InterviewSessionResponse:
    """Update a session's status and/or completed_at.

    Enforces valid status transitions; an invalid transition yields ``409``.
    Same ``404``/``403``/``422`` rules as the other endpoints.
    """
    try:
        interview_session = service.update_session(
            current_user, employee_id, session_id, data
        )
    except (EmployeeError, InterviewSessionError) as exc:
        raise _to_http_exception(exc)
    return InterviewSessionResponse.model_validate(interview_session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an interview session",
    responses=_OWNERSHIP_RESPONSES,
)
def delete_session(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewSessionServiceDep,
) -> None:
    """Delete a session by id, scoped to the employee.

    Returns ``204 No Content`` on success. Same ``404``/``403``/``422`` rules
    as the GET endpoint.
    """
    try:
        service.delete_session(current_user, employee_id, session_id)
    except (EmployeeError, InterviewSessionError) as exc:
        raise _to_http_exception(exc)
