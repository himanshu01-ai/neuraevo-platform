"""Interview session-question API endpoints (progress within a session)."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    CurrentUserDep,
    InterviewSessionQuestionServiceDep,
)
from app.schemas.interview_session_question import (
    SessionQuestionCreate,
    SessionQuestionResponse,
    SessionQuestionUpdate,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)
from app.services.interview_question_service import (
    InterviewQuestionError,
    InterviewQuestionNotFoundError,
)
from app.services.interview_session_question_service import (
    InterviewSessionQuestionAlreadyExistsError,
    InterviewSessionQuestionError,
    InterviewSessionQuestionNotFoundError,
    InterviewSessionQuestionStateError,
)
from app.services.interview_session_service import (
    InterviewSessionError,
    InterviewSessionNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/sessions/{session_id}/questions",
    tags=["Interview Session Questions"],
)

_OWNERSHIP_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": (
            "The employee, session, question, or session-question does not exist."
        )
    },
}

_CREATE_RESPONSES = {
    **_OWNERSHIP_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "description": "The question is already linked to this session."
    },
}

_UPDATE_RESPONSES = {
    **_OWNERSHIP_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "description": "Invalid session-question status transition."
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
        InterviewQuestionNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Interview question not found.",
    ),
    (
        InterviewSessionQuestionNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Session question not found.",
    ),
    (
        InterviewSessionQuestionAlreadyExistsError,
        status.HTTP_409_CONFLICT,
        "This question is already linked to the session.",
    ),
    (
        InterviewSessionQuestionStateError,
        status.HTTP_409_CONFLICT,
        "Invalid session-question status transition.",
    ),
]

_DomainError = (
    EmployeeError
    | InterviewSessionError
    | InterviewQuestionError
    | InterviewSessionQuestionError
)


def _to_http_exception(exc: _DomainError) -> HTTPException:
    """Translate an ownership/lookup/state domain error into an HTTPException."""
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            detail_msg = (
                str(exc)
                if isinstance(exc, InterviewSessionQuestionStateError)
                else detail
            )
            return HTTPException(status_code=code, detail=detail_msg)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=SessionQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a question into an interview session",
    responses=_CREATE_RESPONSES,
)
def create_session_question(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    data: SessionQuestionCreate,
    current_user: CurrentUserDep,
    service: InterviewSessionQuestionServiceDep,
) -> SessionQuestionResponse:
    """Link a question into the session (status defaults to ``pending``).

    The employee must own both the session and the question. Returns ``409``
    if the question is already linked to this session.
    """
    try:
        session_question = service.create_session_question(
            current_user, employee_id, session_id, data
        )
    except (
        EmployeeError,
        InterviewSessionError,
        InterviewQuestionError,
        InterviewSessionQuestionError,
    ) as exc:
        raise _to_http_exception(exc)
    return SessionQuestionResponse.model_validate(session_question)


@router.get(
    "",
    response_model=List[SessionQuestionResponse],
    summary="List the questions linked to an interview session",
    responses=_OWNERSHIP_RESPONSES,
)
def list_session_questions(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewSessionQuestionServiceDep,
) -> List[SessionQuestionResponse]:
    """List the session's question links, ordered by created_at."""
    try:
        session_questions = service.list_session_questions(
            current_user, employee_id, session_id
        )
    except (
        EmployeeError,
        InterviewSessionError,
        InterviewQuestionError,
        InterviewSessionQuestionError,
    ) as exc:
        raise _to_http_exception(exc)
    return [
        SessionQuestionResponse.model_validate(sq) for sq in session_questions
    ]


@router.get(
    "/{session_question_id}",
    response_model=SessionQuestionResponse,
    summary="Get a single session question",
    responses=_OWNERSHIP_RESPONSES,
)
def get_session_question(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    session_question_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewSessionQuestionServiceDep,
) -> SessionQuestionResponse:
    """Return a single session-question by id, scoped to the session.

    Returns ``404`` if it does not exist or belongs to a different session.
    Invalid path UUIDs yield ``422``.
    """
    try:
        session_question = service.get_session_question(
            current_user, employee_id, session_id, session_question_id
        )
    except (
        EmployeeError,
        InterviewSessionError,
        InterviewQuestionError,
        InterviewSessionQuestionError,
    ) as exc:
        raise _to_http_exception(exc)
    return SessionQuestionResponse.model_validate(session_question)


@router.patch(
    "/{session_question_id}",
    response_model=SessionQuestionResponse,
    summary="Update a session question's status",
    responses=_UPDATE_RESPONSES,
)
def update_session_question(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    session_question_id: uuid.UUID,
    data: SessionQuestionUpdate,
    current_user: CurrentUserDep,
    service: InterviewSessionQuestionServiceDep,
) -> SessionQuestionResponse:
    """Update a session-question's status, enforcing valid transitions.

    An invalid transition yields ``409``. Same ``404``/``403``/``422`` rules as
    the other endpoints.
    """
    try:
        session_question = service.update_session_question(
            current_user, employee_id, session_id, session_question_id, data
        )
    except (
        EmployeeError,
        InterviewSessionError,
        InterviewQuestionError,
        InterviewSessionQuestionError,
    ) as exc:
        raise _to_http_exception(exc)
    return SessionQuestionResponse.model_validate(session_question)


@router.delete(
    "/{session_question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a question from an interview session",
    responses=_OWNERSHIP_RESPONSES,
)
def delete_session_question(
    employee_id: uuid.UUID,
    session_id: uuid.UUID,
    session_question_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewSessionQuestionServiceDep,
) -> None:
    """Remove a question link from the session.

    Returns ``204 No Content`` on success. Same ``404``/``403``/``422`` rules
    as the GET endpoint.
    """
    try:
        service.delete_session_question(
            current_user, employee_id, session_id, session_question_id
        )
    except (
        EmployeeError,
        InterviewSessionError,
        InterviewQuestionError,
        InterviewSessionQuestionError,
    ) as exc:
        raise _to_http_exception(exc)
