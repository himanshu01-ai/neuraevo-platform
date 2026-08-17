"""ORM models for the record of what a workflow actually did (Sprint 18.10).

Three tables that turn a run from a one-time answer into something that can be
looked back at: the run itself, what each step did, and what was worth saying
while it happened.

The defining rule is that **history is immutable**. A row is written once, when
the run is over, and never updated — a retry is a *new* run that points back at
the one it repeats. That is what makes "what ran last Tuesday" a question with a
stable answer, and it is why nothing here has an ``updated_at``.

These record the runtime's output; they do not extend it. Every column is
something Sprint 15.15 already produces or something the execution service
observes from outside — the coordinator is not touched, and nothing here changes
how a workflow runs.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workflow import Workflow


class WorkflowExecution(Base):
    """One run of one workflow, as it turned out.

    Identity is the point. Before this, a run had no id of its own — the
    coordinator was handed the *workflow's* id and its result echoed that back,
    so two runs of the same workflow were indistinguishable once the response
    was gone. This row is that missing identity, and everything else hangs off
    it.

    Timings are measured by the execution service around the coordinator rather
    than reported by it: the runtime records no clock, and giving it one would
    mean changing an engine this sprint must not touch.
    """

    __tablename__ = "workflow_executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Who ran it. Recorded even though ownership is currently the workflow's,
    # because "who did this" is the question history exists to answer and
    # deriving it from the workflow would stop being true the moment a workflow
    # can be run by anyone but its owner.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # The runtime's own vocabulary (``COMPLETED`` / ``FAILED``), stored as text
    # exactly as ``Workflow.status`` stores its lifecycle. Kept as the runtime
    # writes it so history never disagrees with the engine that made it.
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Stored rather than derived from the two timestamps: it is read on every
    # history row, and a stored integer cannot drift with timezone handling.
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    total_step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_step_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    #: The step that stopped the run. ``None`` when it finished.
    failed_step_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: Why it stopped, in the runtime's words. ``None`` when it finished.
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    #: How this run was started — ``manual`` or ``retry``.
    trigger: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    #: The run this one repeats, when it is a retry. A retry never edits the
    #: run it repeats; it points at it.
    retry_of_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("workflow_executions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Deliberately no ``updated_at``: a finished run does not change.

    workflow: Mapped["Workflow"] = relationship()
    owner: Mapped["User"] = relationship()
    steps: Mapped[List["WorkflowExecutionStep"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="WorkflowExecutionStep.position",
    )
    logs: Mapped[List["WorkflowExecutionLog"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="WorkflowExecutionLog.sequence",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<WorkflowExecution id={self.id} status={self.status!r}>"


class WorkflowExecutionStep(Base):
    """What one step did within a run.

    A near-copy of the runtime's :class:`CapabilityExecutionReference`, plus the
    timings and ordering the runtime does not carry. Two of these columns hold
    information the API has been discarding since Sprint 18.6 —
    ``execution_metadata`` and the artifact descriptors — which cost nothing to
    keep now that there is somewhere to keep them.
    """

    __tablename__ = "workflow_execution_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    #: The authored node's id — how a step joins back to the graph that made it.
    step_id: Mapped[str] = mapped_column(String(255), nullable=False)
    capability: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    #: Where it came in the run. The graph's order is not the run's order — the
    #: runtime sorts a DAG into a sequence — so the position it actually ran in
    #: is recorded rather than recomputed later from a graph that may since have
    #: been edited.
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    #: The capability's plain outputs, as returned.
    outputs: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    #: The runtime's per-step descriptors, which the execution response drops.
    step_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    #: Plain descriptors of what the step produced, which the response also
    #: drops. Descriptors only — no artifact contents are copied here.
    artifacts: Mapped[List[Any]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    execution: Mapped["WorkflowExecution"] = relationship(back_populates="steps")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<WorkflowExecutionStep step_id={self.step_id!r} status={self.status!r}>"


class WorkflowExecutionLog(Base):
    """One thing worth saying about a run, as a record rather than a line of text.

    Structured on purpose: a level, a message, and the step it belongs to, so
    the UI can filter and order them without parsing prose. The service writes
    these; they are never a dump of the Python logger, and never a stack trace —
    an internal traceback tells the person who ran a workflow nothing and
    describes the server to them, so the message is the one already written for
    a person.
    """

    __tablename__ = "workflow_execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    #: Ordering within the run. An explicit counter rather than a timestamp:
    #: several records can share a millisecond, and their order still matters.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    #: ``info`` / ``warning`` / ``error``.
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    #: The step this concerns, when it concerns one.
    step_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    execution: Mapped["WorkflowExecution"] = relationship(back_populates="logs")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<WorkflowExecutionLog level={self.level!r} step_id={self.step_id!r}>"
