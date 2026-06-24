"""Interview answer API endpoints (nested under a blueprint question).

Each question has at most one answer, so these endpoints address the singular
``/answer`` sub-resource without an answer id in the path.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUserDep, InterviewAnswerServiceDep
from app.schemas.interview_answer import (
    InterviewAnswerCreate,
    InterviewAnswerResponse,
    InterviewAnswerUpdate,
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
from app.services.interview_answer_service import (
    InterviewAnswerAlreadyExistsError,
    InterviewAnswerError,
    InterviewAnswerNotFoundError,
)
from app.services.interview_question_service import (
    InterviewQuestionError,
    InterviewQuestionNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/blueprint/questions/{question_id}/answer",
    tags=["Interview Answers"],
)

_OWNERSHIP_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee, blueprint, question, or answer does not exist."
    },
}

_CREATE_RESPONSES = {
    **_OWNERSHIP_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "description": "The question already has an answer."
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
    (
        InterviewAnswerNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Interview answer not found.",
    ),
    (
        InterviewAnswerAlreadyExistsError,
        status.HTTP_409_CONFLICT,
        "This question already has an answer.",
    ),
]


def _to_http_exception(
    exc: EmployeeError | BlueprintError | InterviewQuestionError | InterviewAnswerError,
) -> HTTPException:
    """Translate an ownership/lookup domain error into an HTTPException."""
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=InterviewAnswerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the answer for a blueprint question",
    responses=_CREATE_RESPONSES,
)
def create_answer(
    employee_id: uuid.UUID,
    question_id: uuid.UUID,
    data: InterviewAnswerCreate,
    current_user: CurrentUserDep,
    service: InterviewAnswerServiceDep,
) -> InterviewAnswerResponse:
    """Create the question's single answer.

    Returns ``409`` if the question already has an answer, ``404``/``403`` for
    the employee -> blueprint -> question chain, and ``422`` for invalid input.
    """
    try:
        answer = service.create_answer(
            current_user, employee_id, question_id, data
        )
    except (
        EmployeeError,
        BlueprintError,
        InterviewQuestionError,
        InterviewAnswerError,
    ) as exc:
        raise _to_http_exception(exc)
    return InterviewAnswerResponse.model_validate(answer)


@router.get(
    "",
    response_model=InterviewAnswerResponse,
    summary="Get the answer for a blueprint question",
    responses=_OWNERSHIP_RESPONSES,
)
def get_answer(
    employee_id: uuid.UUID,
    question_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewAnswerServiceDep,
) -> InterviewAnswerResponse:
    """Return the question's answer, or ``404`` if it has none."""
    try:
        answer = service.get_answer(current_user, employee_id, question_id)
    except (
        EmployeeError,
        BlueprintError,
        InterviewQuestionError,
        InterviewAnswerError,
    ) as exc:
        raise _to_http_exception(exc)
    return InterviewAnswerResponse.model_validate(answer)


@router.patch(
    "",
    response_model=InterviewAnswerResponse,
    summary="Update the answer for a blueprint question",
    responses=_OWNERSHIP_RESPONSES,
)
def update_answer(
    employee_id: uuid.UUID,
    question_id: uuid.UUID,
    data: InterviewAnswerUpdate,
    current_user: CurrentUserDep,
    service: InterviewAnswerServiceDep,
) -> InterviewAnswerResponse:
    """Partially update the question's answer.

    Returns ``404`` if the question has no answer, ``404``/``403`` for the
    ownership chain.
    """
    try:
        answer = service.update_answer(
            current_user, employee_id, question_id, data
        )
    except (
        EmployeeError,
        BlueprintError,
        InterviewQuestionError,
        InterviewAnswerError,
    ) as exc:
        raise _to_http_exception(exc)
    return InterviewAnswerResponse.model_validate(answer)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the answer for a blueprint question",
    responses=_OWNERSHIP_RESPONSES,
)
def delete_answer(
    employee_id: uuid.UUID,
    question_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: InterviewAnswerServiceDep,
) -> None:
    """Delete the question's answer.

    Returns ``204 No Content`` on success. Same ``404``/``403`` rules as GET.
    """
    try:
        service.delete_answer(current_user, employee_id, question_id)
    except (
        EmployeeError,
        BlueprintError,
        InterviewQuestionError,
        InterviewAnswerError,
    ) as exc:
        raise _to_http_exception(exc)
