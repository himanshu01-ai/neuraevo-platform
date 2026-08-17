"""Persistence for the platform activity timeline (Sprint 20C).

CRUD-style accessors over :class:`ActivityEvent`. Persistence only: it appends
and reads, and decides nothing about who may see an event — the activity service
enforces that. History is append-only, so there is no update or delete here.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent


class ActivityEventRepository:
    """Append-and-read accessors for :class:`ActivityEvent` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Writes ----------------------------------------------------------

    def next_sequence(self, resource_type: str, resource_id: uuid.UUID) -> int:
        """The next per-resource ordinal (1-based)."""
        stmt = select(func.max(ActivityEvent.sequence)).where(
            ActivityEvent.resource_type == resource_type,
            ActivityEvent.resource_id == resource_id,
        )
        current = self.session.scalar(stmt)
        return (current or 0) + 1

    def add(self, event: ActivityEvent) -> ActivityEvent:
        """Append an event and flush so it gets its id/defaults."""
        self.session.add(event)
        self.session.flush()
        return event

    # --- Reads -----------------------------------------------------------

    def list_for_resource(
        self, resource_type: str, resource_id: uuid.UUID, *, limit: int = 100
    ) -> Sequence[ActivityEvent]:
        """One resource's timeline, newest first."""
        stmt = (
            select(ActivityEvent)
            .where(
                ActivityEvent.resource_type == resource_type,
                ActivityEvent.resource_id == resource_id,
            )
            .order_by(ActivityEvent.sequence.desc())
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def list_owned(
        self, owner_user_id: uuid.UUID, *, limit: int = 100
    ) -> Sequence[ActivityEvent]:
        """Events on resources this user owns, newest first."""
        stmt = (
            select(ActivityEvent)
            .where(ActivityEvent.owner_user_id == owner_user_id)
            .order_by(ActivityEvent.created_at.desc())
            .limit(limit)
        )
        return self.session.scalars(stmt).all()

    def list_for_resource_ids(
        self,
        resource_type: str,
        resource_ids: Sequence[uuid.UUID],
        *,
        limit: int = 100,
    ) -> Sequence[ActivityEvent]:
        """Events on any of the given resources of one type, newest first."""
        if not resource_ids:
            return []
        stmt = (
            select(ActivityEvent)
            .where(
                ActivityEvent.resource_type == resource_type,
                ActivityEvent.resource_id.in_(list(resource_ids)),
            )
            .order_by(ActivityEvent.created_at.desc())
            .limit(limit)
        )
        return self.session.scalars(stmt).all()
