"""Data-access layer for :class:`~app.models.employee_assignment.EmployeeAssignment`.

Persistence only. Assignment is a description of expected work — nothing here
schedules, orders, or runs anything.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee_assignment import EmployeeAssignment
from app.schemas.employee import EmployeeAssignmentCreate


class EmployeeAssignmentRepository:
    """CRUD-style accessors for employee assignments."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_employee(
        self, employee_id: uuid.UUID
    ) -> Sequence[EmployeeAssignment]:
        stmt = (
            select(EmployeeAssignment)
            .where(EmployeeAssignment.employee_id == employee_id)
            .order_by(EmployeeAssignment.created_at)
        )
        return self.session.scalars(stmt).all()

    def count_by_employee(self, employee_id: uuid.UUID) -> int:
        return len(self.list_by_employee(employee_id))

    def get_by_id(
        self, assignment_id: uuid.UUID
    ) -> Optional[EmployeeAssignment]:
        return self.session.get(EmployeeAssignment, assignment_id)

    def get_by_workflow(
        self, employee_id: uuid.UUID, workflow_id: str
    ) -> Optional[EmployeeAssignment]:
        stmt = select(EmployeeAssignment).where(
            EmployeeAssignment.employee_id == employee_id,
            EmployeeAssignment.workflow_id == workflow_id,
        )
        return self.session.scalar(stmt)

    def create(
        self, employee_id: uuid.UUID, data: EmployeeAssignmentCreate
    ) -> EmployeeAssignment:
        assignment = EmployeeAssignment(
            employee_id=employee_id,
            workflow_id=data.workflow_id,
            workflow_name=data.workflow_name,
            priority=data.priority.value,
            execution_mode=data.execution_mode.value,
            dependency_summary=data.dependency_summary,
        )
        self.session.add(assignment)
        self.session.flush()
        self.session.refresh(assignment)
        return assignment

    def delete(self, assignment: EmployeeAssignment) -> None:
        self.session.delete(assignment)
        self.session.flush()

