"""SQLAlchemy ORM models for the Task Engine (Sprint 19).

A task is first-class executable work: a named piece of work a user describes,
optionally assigns to an AI employee, optionally shapes with a workflow, and —
when it has a workflow — launches through the existing Workflow Execution
Service. Nothing here runs anything: the Sprint 15.15 runtime coordinator and
the Sprint 18.6 execution service own running, and this domain only records
what a task is, who carries it, and which runs it launched.

Two tables:

* ``tasks`` — the work itself, owned by exactly one user.
* ``task_workflow_executions`` — which recorded runs a task launched. A link
  table rather than a ``task_id`` column on ``workflow_executions``, because
  execution history is a completed, immutable domain (Sprint 18.10) that this
  sprint must not modify. A task's history is a join, never a copy.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import EmployeePriority, TaskExecutionMode, TaskStatus

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.user import User
    from app.models.workflow import Workflow
    from app.models.workflow_execution import WorkflowExecution


class Task(Base):
    """One piece of work, described by its owner.

    Ownership is the user's: the creator owns the task, and every other
    reference — the assignee employee, the attached workflow — must belong to
    that same user, validated in the service layer against the existing
    ownership chains.

    ``employee_id`` and ``workflow_id`` are ``SET NULL`` on delete rather than
    cascading: deleting an employee or a workflow retires a collaborator, not
    the work itself. The task survives, unassigned or unshaped, and says so.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    #: The AI employee carrying the work. ``None`` until assigned.
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    #: The workflow shaping the work. ``None`` until attached.
    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("workflows.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    #: The id a person quotes (``TSK-1041``). Assigned by the service at
    #: creation, sequential per owner, and never reused.
    business_id: Mapped[str] = mapped_column(String(50), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stored as plain strings; allowed values are defined by
    # ``app.utils.constants`` and validated at the schema and service layers,
    # matching how ``Workflow.status`` and ``Employee.status`` are handled.
    status: Mapped[str] = mapped_column(
        String(50), default=TaskStatus.PENDING.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(50), default=EmployeePriority.MEDIUM.value, nullable=False
    )
    execution_mode: Mapped[str] = mapped_column(
        String(50), default=TaskExecutionMode.MANUAL.value, nullable=False
    )

    #: 0–100, written by the service from what a run reported. Never estimated.
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped["User"] = relationship()
    assignee: Mapped[Optional["Employee"]] = relationship()
    workflow: Mapped[Optional["Workflow"]] = relationship()
    execution_links: Mapped[List["TaskWorkflowExecution"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskWorkflowExecution.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Task id={self.id} name={self.name!r} status={self.status!r}>"


class TaskWorkflowExecution(Base):
    """One recorded run a task launched.

    Written when the task's execute action hands the workflow to the existing
    execution service and a run comes back recorded. Append-only, like the
    history it points at: a link records that a launch happened, so it is never
    updated or repointed.

    ``execution_id`` is unique — a run is launched by at most one task — and
    cascades with the execution row, so history's own deletion rules keep the
    links honest without this table adding any of its own.
    """

    __tablename__ = "task_workflow_executions"
    __table_args__ = (
        UniqueConstraint("execution_id", name="uq_task_workflow_execution"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="execution_links")
    execution: Mapped["WorkflowExecution"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<TaskWorkflowExecution task_id={self.task_id} "
            f"execution_id={self.execution_id}>"
        )
