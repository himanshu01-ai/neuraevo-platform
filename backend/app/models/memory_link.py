"""SQLAlchemy ORM models linking existing memories to tasks and workflows.

Memory integration is done by *reference*, not restructuring. The Sprint 2
:class:`~app.models.memory.Memory` is employee-owned and stays exactly as it
was; these two link tables record that a task or a workflow *uses* an existing
memory, so a memory becomes a shared platform resource without a second copy of
its content and without touching its ownership chain.

Two tables, one per association:

* ``task_memory_links`` — which memories a task references (reference documents,
  execution notes, task knowledge).
* ``workflow_memory_links`` — which memories a workflow references (reference
  material, documentation, reusable execution context).

Both mirror the Sprint 19 ``task_workflow_executions`` link-table pattern: a
plain association row, unique per pair, that cascades from either side. Deleting
the task/workflow, or the memory, removes the link; neither deletion destroys
the other side. The relationships are unidirectional (no ``back_populates``), so
the frozen ``Memory``, ``Task`` and ``Workflow`` models are left unmodified.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.memory import Memory
    from app.models.task import Task
    from app.models.workflow import Workflow


class TaskMemoryLink(Base):
    """One memory a task references.

    ``memory_id`` and ``task_id`` both cascade on delete: the link is an
    association over rows that own themselves, so it never outlives either end
    and never keeps either end alive. Unique per ``(task_id, memory_id)`` — a
    task references a memory at most once; attaching an already-linked memory is
    a no-op, not a duplicate.
    """

    __tablename__ = "task_memory_links"
    __table_args__ = (
        UniqueConstraint("task_id", "memory_id", name="uq_task_memory_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("memories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    #: Unidirectional — no ``back_populates``, so ``Task`` and ``Memory`` are
    #: untouched. Loaded when the service reads a task's referenced memories.
    task: Mapped["Task"] = relationship()
    memory: Mapped["Memory"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<TaskMemoryLink task_id={self.task_id} memory_id={self.memory_id}>"
        )


class WorkflowMemoryLink(Base):
    """One memory a workflow references.

    Same shape and same rules as :class:`TaskMemoryLink`, for the workflow side:
    unique per ``(workflow_id, memory_id)``, cascading from either end,
    unidirectional so the frozen ``Workflow`` and ``Memory`` models are
    unchanged.
    """

    __tablename__ = "workflow_memory_links"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "memory_id", name="uq_workflow_memory_link"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("memories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workflow: Mapped["Workflow"] = relationship()
    memory: Mapped["Memory"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<WorkflowMemoryLink workflow_id={self.workflow_id} "
            f"memory_id={self.memory_id}>"
        )
