"""SQLAlchemy ORM model for authored workflows owned by users."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.utils.constants import WorkflowStatus

if TYPE_CHECKING:
    from app.models.user import User


class Workflow(Base):
    """A workflow definition belonging to a single owning user.

    Authoring only. This records the *structure* a user drew — nodes, edges and
    settings — and nothing here schedules, orders, starts, or runs anything.
    The Sprint 15.15 runtime coordinator executes steps handed to it and does
    not read this table; connecting the two is a later sprint.

    The graph is stored as one validated JSON document rather than normalised
    into node and edge tables. The builder loads and saves a whole graph every
    time, no query targets an individual node, and node shape is still the
    frontend's authoring vocabulary — so rows per node would buy constraints
    nobody needs and cost a join on every read. ``app.services.workflow_graph``
    validates the structure before it is ever persisted.
    """

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stored as a plain string; allowed values are defined by
    # ``app.utils.constants.WorkflowStatus`` and validated at the schema and
    # service layers, matching how ``Employee.status`` is handled.
    status: Mapped[str] = mapped_column(
        String(50), default=WorkflowStatus.DRAFT.value, nullable=False
    )

    # ``JSON`` rather than ``JSONB``: the model stays portable across the
    # SQLite used by tests and the PostgreSQL used in production. Nothing
    # queries *inside* the document, so the indexing JSONB would enable has no
    # consumer; the migration can move to JSONB if one ever appears.
    graph: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # A reversible retirement, mirroring ``Employee.archived_at``. There is no
    # soft delete here: a workflow owns nothing that must outlive it, so
    # ``DELETE`` removes the row.
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Each workflow belongs to exactly one owning user.
    owner: Mapped["User"] = relationship(back_populates="workflows")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Workflow id={self.id} name={self.name!r} user_id={self.user_id}>"
