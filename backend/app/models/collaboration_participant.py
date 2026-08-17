"""SQLAlchemy ORM model for collaboration participants (Sprint 20).

A participant is one collaborator on one shared resource. The row is
*polymorphic over the resource*: ``resource_type`` + ``resource_id`` name a
conversation, task, workflow, or memory without a foreign key to any of them,
so a single participant model serves every domain and a future domain joins by
naming a new :class:`~app.utils.constants.CollaborationResourceType`. There is
deliberately no ``resource`` relationship — the four owning models
(``Conversation``, ``Task``, ``Workflow``, ``Memory``) are frozen and stay
untouched; collaboration attaches to them by reference, exactly as the Sprint
19/Sprint 20 memory-link tables attach to memories.

The *participant side* keeps real integrity: a participant is always either a
user or an AI employee, so two nullable foreign keys carry the identity and a
check constraint enforces that exactly one is set and matches
``participant_type``. That AI-employee column is what lets an employee join a
resource on the same footing as a person.

``owner`` is never stored here. The resource's owner comes from its existing
ownership chain, read back at access-resolution time; a participant row records
only the *additional* collaborators an owner has invited.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import CollaborationRole, ParticipantType

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.user import User


class CollaborationParticipant(Base):
    """One collaborator on one shared resource.

    ``resource_type`` and ``role`` are plain strings whose allowed values are
    :class:`~app.utils.constants.CollaborationResourceType` and
    :class:`~app.utils.constants.CollaborationRole`, validated at the schema and
    service layers — the same convention every status/kind column in the
    codebase follows. ``resource_id`` carries no foreign key because the
    referenced table varies by ``resource_type``; the service validates that the
    resource exists and resolves its owner through the domain's own service.

    A user appears at most once per resource, and an employee at most once per
    resource, enforced by the two unique constraints. Because SQLite and
    PostgreSQL both treat ``NULL`` as distinct, an employee row (``user_id``
    null) never collides on the user constraint, and vice versa.
    """

    __tablename__ = "collaboration_participants"
    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "resource_id",
            "user_id",
            name="uq_collab_participant_user",
        ),
        UniqueConstraint(
            "resource_type",
            "resource_id",
            "employee_id",
            name="uq_collab_participant_employee",
        ),
        # Exactly one identity is set, and it matches the declared type. A
        # participant is a user xor an employee — never both, never neither.
        CheckConstraint(
            "(participant_type = 'user' AND user_id IS NOT NULL "
            "AND employee_id IS NULL) OR "
            "(participant_type = 'employee' AND employee_id IS NOT NULL "
            "AND user_id IS NULL)",
            name="ck_collab_participant_identity",
        ),
        # Listing a resource's participants is the hot read; index the pair.
        Index("ix_collab_participant_resource", "resource_type", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    participant_type: Mapped[str] = mapped_column(String(50), nullable=False)

    #: Set when the participant is a user; null when it is an employee. Cascades
    #: with the user, so deleting a user removes their collaborations.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    #: Set when the participant is an AI employee; null when it is a user.
    #: Cascades with the employee, so retiring an employee removes it from the
    #: resources it collaborated on.
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("employees.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(50), default=CollaborationRole.VIEWER.value, nullable=False
    )

    #: The user who added this participant — always the resource owner in this
    #: sprint. Recorded so the activity timeline (a later slice) can say who
    #: invited whom without inferring it.
    added_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
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

    #: Identity-only relationships. No ``back_populates`` — ``User`` and
    #: ``Employee`` are not taught about collaboration, so they stay unchanged.
    user: Mapped[Optional["User"]] = relationship(foreign_keys=[user_id])
    employee: Mapped[Optional["Employee"]] = relationship(foreign_keys=[employee_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        identity = self.user_id if self.participant_type == ParticipantType.USER.value else self.employee_id
        return (
            f"<CollaborationParticipant resource={self.resource_type}:{self.resource_id} "
            f"{self.participant_type}={identity} role={self.role!r}>"
        )
