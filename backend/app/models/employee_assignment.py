"""SQLAlchemy ORM model for work assigned to an AI employee."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import EmployeePriority, ExecutionMode

if TYPE_CHECKING:
    from app.models.employee import Employee


class EmployeeAssignment(Base):
    """A named piece of work an employee is assigned to.

    Foundation only. Assignment is a *description* — this records that an
    employee is expected to work on something, and nothing here schedules,
    orders, starts, or runs anything.

    ``workflow_id`` deliberately carries no foreign key: there is no workflow
    table in this domain yet, so it holds the identifier the caller supplies
    and gains a constraint when a workflow domain exists.
    """

    __tablename__ = "employee_assignments"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "workflow_id", name="uq_employee_assignment_workflow"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(
        String(50), default=EmployeePriority.MEDIUM.value, nullable=False
    )
    execution_mode: Mapped[str] = mapped_column(
        String(50), default=ExecutionMode.SEQUENTIAL.value, nullable=False
    )
    # Plain-language note on what this assignment waits for. Supplied by the
    # caller; never computed here.
    dependency_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    employee: Mapped["Employee"] = relationship(back_populates="assignments")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<EmployeeAssignment employee_id={self.employee_id} "
            f"workflow_id={self.workflow_id!r}>"
        )

