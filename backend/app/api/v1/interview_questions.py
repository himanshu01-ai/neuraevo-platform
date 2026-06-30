"""Interview question API endpoints (nested under an employee's blueprint)."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUserDep, InterviewQuestionServiceDep
from app.schemas.interview_question import (
    InterviewQuestionCreate,
    InterviewQuestionResponse,
)
from app.services.blueprint_service import (
    BlueprintAccessDeniedError,
    BlueprintError,
    BlueprintNotFoundError,
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

router = APIRouter(
    prefix="/employees/{employee_id}/blueprint/questions",
    tags=["Interview Questions"],
)

_OWNERSHIP_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee, blueprint, or question does not exist."
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
    (BlueprintNotFoundError, status.HTTP_404_NOT_FOUND, "Blueprint not found."),
    (
        BlueprintAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this blueprint.",
    ),
    (
        InterviewQuestionNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Interview question not found.",
    ),
]


def _to_http_exception(
    exc: EmployeeError | BlueprintError | InterviewQuestionError,
) -> HTTPException:
    """Translate an ownership/lookup domain error into an HTTPException."""
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=InterviewQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an interview question to the employee's blueprint",
    responses=_OWNERSHIP_RESPONSES,
)
def create_question(
    employee_id: uuid.UUID,
    data: InterviewQuestionCreate,
    current_user: CurrentUserDep,
    service: InterviewQuestionServiceDep,
) -> InterviewQuestionResponse:
    """Create an interview question on the employee's blueprint.

    Requires the employee (and its blueprint) to belong to the authenticated
    user. Returns ``404`` if the employee or blueprint is missing, ``403`` for
    ownership violations, ``422`` for invalid input.
    """
    try:
        question = service.create_question(current_user, employee_id, data)
    except (EmployeeError, BlueprintError, InterviewQuestionError) as exc:
        raise _to_http_exception(exc)
    return InterviewQuestionResponse.model_validate(question)


@router.get(
    "",
    response_model=List[InterviewQuestionResponse],
    summary="List interview questions for the employee's blueprint",
    responses=_OWNERSHIP_RESPONSES,
)
def list_questions(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewQuestionServiceDep,
) -> List[InterviewQuestionResponse]:
    """List the blueprint's questions ordered by ``question_order``.

    Returns an empty list if the blueprint has no questions.
    """
    try:
        questions = service.list_questions(current_user, employee_id)
    except (EmployeeError, BlueprintError, InterviewQuestionError) as exc:
        raise _to_http_exception(exc)
    return [InterviewQuestionResponse.model_validate(q) for q in questions]


@router.get(
    "/{question_id}",
    response_model=InterviewQuestionResponse,
    summary="Get a single interview question for the employee's blueprint",
    responses=_OWNERSHIP_RESPONSES,
)
def get_question(
    employee_id: uuid.UUID,
    question_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewQuestionServiceDep,
) -> InterviewQuestionResponse:
    """Return a single question by id, scoped to the employee's blueprint.

    Returns ``404`` if the question does not exist or belongs to a different
    blueprint. Invalid path UUIDs yield ``422``.
    """
    try:
        question = service.get_question(current_user, employee_id, question_id)
    except (EmployeeError, BlueprintError, InterviewQuestionError) as exc:
        raise _to_http_exception(exc)
    return InterviewQuestionResponse.model_validate(question)


@router.delete(
    "/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a single interview question for the employee's blueprint",
    responses=_OWNERSHIP_RESPONSES,
)
def delete_question(
    employee_id: uuid.UUID,
    question_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewQuestionServiceDep,
) -> None:
    """Delete a question by id, scoped to the employee's blueprint.

    Returns ``204 No Content`` on success. Same ``404``/``403``/``422`` rules
    as the GET endpoint.
    """
    try:
        service.delete_question(current_user, employee_id, question_id)
    except (EmployeeError, BlueprintError, InterviewQuestionError) as exc:
        raise _to_http_exception(exc)
