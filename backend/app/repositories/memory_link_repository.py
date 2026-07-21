"""Data-access layer for memory ↔ task/workflow links and user-wide reads.

Persistence only — no ownership checks, no authorization, no business rules.
Transaction control is left to the caller; write methods ``flush`` so generated
values are populated. The Sprint 2 :class:`~app.repositories.memory_repository.
MemoryRepository` is unchanged; this repository owns the new link tables and the
one query the Memory Engine never had: reading a *user's* memories across all
their employees (the shared-resource list and its keyword search).
"""

import uuid
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.memory import Memory
from app.models.memory_link import TaskMemoryLink, WorkflowMemoryLink


class MemoryLinkRepository:
    """CRUD-style accessors for the two link tables and user-wide memory reads."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Task links ------------------------------------------------------

    def get_task_link(
        self, task_id: uuid.UUID, memory_id: uuid.UUID
    ) -> Optional[TaskMemoryLink]:
        stmt = select(TaskMemoryLink).where(
            TaskMemoryLink.task_id == task_id,
            TaskMemoryLink.memory_id == memory_id,
        )
        return self.session.scalars(stmt).first()

    def add_task_link(
        self, task_id: uuid.UUID, memory_id: uuid.UUID
    ) -> TaskMemoryLink:
        link = TaskMemoryLink(task_id=task_id, memory_id=memory_id)
        self.session.add(link)
        self.session.flush()
        return link

    def delete_task_link(self, link: TaskMemoryLink) -> None:
        self.session.delete(link)
        self.session.flush()

    def list_task_memories(
        self, task_id: uuid.UUID
    ) -> Sequence[Tuple[Memory, str]]:
        """The memories a task references with each owning employee's name.

        Ordered by when the link was made (oldest first), so the list reads in
        the order the user built it. Returns ``(Memory, employee_name)`` rows.
        """
        stmt = (
            select(Memory, Employee.name)
            .join(TaskMemoryLink, TaskMemoryLink.memory_id == Memory.id)
            .join(Employee, Employee.id == Memory.employee_id)
            .where(TaskMemoryLink.task_id == task_id)
            .order_by(TaskMemoryLink.created_at)
        )
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    # --- Workflow links --------------------------------------------------

    def get_workflow_link(
        self, workflow_id: uuid.UUID, memory_id: uuid.UUID
    ) -> Optional[WorkflowMemoryLink]:
        stmt = select(WorkflowMemoryLink).where(
            WorkflowMemoryLink.workflow_id == workflow_id,
            WorkflowMemoryLink.memory_id == memory_id,
        )
        return self.session.scalars(stmt).first()

    def add_workflow_link(
        self, workflow_id: uuid.UUID, memory_id: uuid.UUID
    ) -> WorkflowMemoryLink:
        link = WorkflowMemoryLink(workflow_id=workflow_id, memory_id=memory_id)
        self.session.add(link)
        self.session.flush()
        return link

    def delete_workflow_link(self, link: WorkflowMemoryLink) -> None:
        self.session.delete(link)
        self.session.flush()

    def list_workflow_memories(
        self, workflow_id: uuid.UUID
    ) -> Sequence[Tuple[Memory, str]]:
        """The memories a workflow references with each owning employee's name."""
        stmt = (
            select(Memory, Employee.name)
            .join(WorkflowMemoryLink, WorkflowMemoryLink.memory_id == Memory.id)
            .join(Employee, Employee.id == Memory.employee_id)
            .where(WorkflowMemoryLink.workflow_id == workflow_id)
            .order_by(WorkflowMemoryLink.created_at)
        )
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    # --- User-wide memory reads (the shared-resource list + search) ------

    def search_user_memories(
        self,
        user_id: uuid.UUID,
        *,
        keyword: Optional[str] = None,
        memory_type: Optional[str] = None,
        min_importance: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Tuple[Memory, str]]:
        """All of a user's memories, across every one of their employees.

        Joins ``memories`` to ``employees`` and filters by owner, so a memory is
        addressable without first naming the employee that holds it — the shared
        resource the platform reads. ``keyword`` is a case-insensitive substring
        scan over ``content``; ``memory_type`` and ``min_importance`` reuse the
        Memory Engine's own filter semantics. Soft-deleted employees' memories
        are excluded. Newest first. Returns ``(Memory, employee_name)`` rows.
        """
        stmt = (
            select(Memory, Employee.name)
            .join(Employee, Employee.id == Memory.employee_id)
            .where(Employee.user_id == user_id, Employee.deleted_at.is_(None))
        )
        if keyword:
            stmt = stmt.where(Memory.content.ilike(f"%{keyword}%"))
        if memory_type is not None:
            stmt = stmt.where(Memory.memory_type == memory_type)
        if min_importance is not None:
            stmt = stmt.where(Memory.importance_score >= min_importance)
        stmt = (
            stmt.order_by(Memory.created_at.desc()).offset(offset).limit(limit)
        )
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    def get_user_memory(
        self, user_id: uuid.UUID, memory_id: uuid.UUID
    ) -> Optional[Tuple[Memory, str]]:
        """One of the user's memories by id, with its owning employee's name.

        Scoped through the employee ownership join so a memory belonging to
        another user (or a soft-deleted employee) is simply not found here.
        """
        stmt = (
            select(Memory, Employee.name)
            .join(Employee, Employee.id == Memory.employee_id)
            .where(
                Memory.id == memory_id,
                Employee.user_id == user_id,
                Employee.deleted_at.is_(None),
            )
        )
        row = self.session.execute(stmt).first()
        return (row[0], row[1]) if row is not None else None

    def count_user_memories(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count(Memory.id))
            .join(Employee, Employee.id == Memory.employee_id)
            .where(Employee.user_id == user_id, Employee.deleted_at.is_(None))
        )
        return int(self.session.scalar(stmt) or 0)
