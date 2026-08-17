"""SQLAlchemy ORM model for the platform activity timeline (Sprint 20C).

One append-only record that something happened to a collaborated resource. It
is the cross-domain counterpart to the Sprint 18.2 ``employee_activity_events``:
same append-only discipline and per-subject ``sequence`` ordinal, but keyed
polymorphically by ``resource_type`` + ``resource_id`` so a single timeline
serves conversations, tasks, workflows, and memory — and any future resource.

Design choices that follow from it being an *audit log*:

* No foreign key on ``resource_id`` (the referenced table varies) and none on
  ``actor_id`` (the event must survive the actor being deleted). History is
  written once and never rewritten.
* ``owner_user_id`` is denormalised from the resource's owner at write time so
  the per-user feed is a single indexed read rather than a fan-out across every
  domain. It is the owner *as of the event*, which is exactly what a feed wants.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActivityEvent(Base):
    """One thing that happened to a collaborated resource.

    ``resource_type``, ``actor_type`` and ``kind`` are plain strings whose
    allowed values are :class:`~app.utils.constants.CollaborationResourceType`,
    :class:`~app.utils.constants.ActivityActorType` and
    :class:`~app.utils.constants.ActivityKind`, validated where events are
    recorded. ``sequence`` is a per-resource ordinal giving a stable order that
    does not depend on timestamp resolution, exactly like the employee timeline.
    """

    __tablename__ = "activity_events"
    __table_args__ = (
        # The resource timeline reads by resource in sequence order.
        Index("ix_activity_resource", "resource_type", "resource_id", "sequence"),
        # The per-user feed reads by owner, newest first.
        Index("ix_activity_owner", "owner_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    #: The resource's owner at the time of the event, denormalised so the user
    #: feed is one indexed query. Nullable only in the defensive case where an
    #: owner could not be resolved; in practice every recorded event has one.
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)

    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    #: The user or employee that acted; ``None`` for system events. No foreign
    #: key — the audit row outlives the actor.
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)

    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<ActivityEvent resource={self.resource_type}:{self.resource_id} "
            f"kind={self.kind!r} sequence={self.sequence}>"
        )
