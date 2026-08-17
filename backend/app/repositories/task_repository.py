"""Data-access layer for :class:`~app.models.task.Task` (Sprint 19).

Persistence only — no business logic, no ownership checks, no state decisions.
Transaction control is left to the caller; methods ``flush`` so generated
values like ``id`` are populated.

Like workflows there is no soft delete: a task owns nothing that must outlive
it — its execution links cascade, and the executions they point at belong to
history, not to the task.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskWorkflowExecution
from app.models.workflow_execution import WorkflowExecution


class TaskRepository:
    """CRUD-style accessors for :class:`Task` rows and their execution links."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Reads -----------------------------------------------------------

    def get_by_id(self, task_id: uuid.UUID) -> Optional[Task]:
        return self.session.get(Task, task_id)

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Task]:
        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at)
            .offset(skip)
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def count_by_user(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count(Task.id)).where(Task.user_id == user_id)
        return int(self.session.scalar(stmt) or 0)

    # --- Writes ----------------------------------------------------------

    def create(
        self,
        user_id: uuid.UUID,
        *,
        business_id: str,
        name: str,
        description: Optional[str],
        status: str,
        priority: str,
        execution_mode: str,
        employee_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> Task:
        """Persist a new task owned by ``user_id``.

        Takes primitives rather than the create schema: duplication builds a
        row from an existing task, not from a request body, and both paths
        should land in the same place.
        """
        task = Task(
            user_id=user_id,
            business_id=business_id,
            name=name,
            description=description,
            status=status,
            priority=priority,
            execution_mode=execution_mode,
            employee_id=employee_id,
            workflow_id=workflow_id,
        )
        self.session.add(task)
        self.session.flush()
        self.session.refresh(task)
        return task

    def update_fields(self, task: Task, **fields: object) -> Task:
        """Assign the supplied attributes. The caller decides which to send."""
        for key, value in fields.items():
            setattr(task, key, value)
        self.session.flush()
        return task

    def delete(self, task: Task) -> None:
        self.session.delete(task)
        self.session.flush()

    # --- Execution links -------------------------------------------------

    def add_execution_link(
        self, task_id: uuid.UUID, execution_id: uuid.UUID
    ) -> TaskWorkflowExecution:
        """Record that ``task_id`` launched the run ``execution_id``."""
        link = TaskWorkflowExecution(task_id=task_id, execution_id=execution_id)
        self.session.add(link)
        self.session.flush()
        return link

    def get_link_for_execution(
        self, execution_id: uuid.UUID
    ) -> Optional[TaskWorkflowExecution]:
        stmt = select(TaskWorkflowExecution).where(
            TaskWorkflowExecution.execution_id == execution_id
        )
        return self.session.scalars(stmt).first()

    def list_executions(
        self,
        task_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[WorkflowExecution]:
        """The runs this task launched, newest first."""
        stmt = (
            select(WorkflowExecution)
            .join(
                TaskWorkflowExecution,
                TaskWorkflowExecution.execution_id == WorkflowExecution.id,
            )
            .where(TaskWorkflowExecution.task_id == task_id)
            .order_by(WorkflowExecution.started_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def count_executions(self, task_id: uuid.UUID) -> int:
        stmt = select(func.count(TaskWorkflowExecution.id)).where(
            TaskWorkflowExecution.task_id == task_id
        )
        return int(self.session.scalar(stmt) or 0)

    def latest_execution(self, task_id: uuid.UUID) -> Optional[WorkflowExecution]:
        """The most recent run this task launched, or ``None``."""
        stmt = (
            select(WorkflowExecution)
            .join(
                TaskWorkflowExecution,
                TaskWorkflowExecution.execution_id == WorkflowExecution.id,
            )
            .where(TaskWorkflowExecution.task_id == task_id)
            .order_by(WorkflowExecution.started_at.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()
