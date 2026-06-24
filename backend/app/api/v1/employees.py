"""Employee API endpoints."""

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUserDep, EmployeeServiceDep
from app.schemas.employee import EmployeeCreate, EmployeeResponse

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an AI employee for the authenticated user",
)
def create_employee(
    data: EmployeeCreate,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    """Create an employee and attach it to the authenticated user.

    Requires a valid Bearer access token; the owner is taken from the token,
    never from the request body.
    """
    employee = service.create_employee(current_user, data)
    return EmployeeResponse.model_validate(employee)
