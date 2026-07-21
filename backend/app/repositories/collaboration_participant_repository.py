"""Persistence for collaboration participants (Sprint 20).

CRUD-style accessors over :class:`CollaborationParticipant`. Persistence only:
this layer runs queries and flushes, and decides nothing about ownership,
access, or whether a participant *may* be added — those are the collaboration
service's job. Following the repository convention used across the codebase, it
``flush``es so the service can commit the surrounding unit of work.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.collaboration_participant import CollaborationParticipant


class CollaborationParticipantRepository:
    """CRUD-style accessors for :class:`CollaborationParticipant` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Reads -----------------------------------------------------------

    def get_by_id(
        self, participant_id: uuid.UUID
    ) -> Optional[CollaborationParticipant]:
        return self.session.get(CollaborationParticipant, participant_id)

    def list_for_resource(
        self, resource_type: str, resource_id: uuid.UUID
    ) -> Sequence[CollaborationParticipant]:
        """Every participant of one resource, oldest first."""
        stmt = (
            select(CollaborationParticipant)
            .where(
                CollaborationParticipant.resource_type == resource_type,
                CollaborationParticipant.resource_id == resource_id,
            )
            .order_by(CollaborationParticipant.created_at)
        )
        return self.session.scalars(stmt).all()

    def get_user_participant(
        self, resource_type: str, resource_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[CollaborationParticipant]:
        """The row for one user on one resource, or ``None``."""
        stmt = select(CollaborationParticipant).where(
            CollaborationParticipant.resource_type == resource_type,
            CollaborationParticipant.resource_id == resource_id,
            CollaborationParticipant.user_id == user_id,
        )
        return self.session.scalars(stmt).first()

    def get_employee_participant(
        self, resource_type: str, resource_id: uuid.UUID, employee_id: uuid.UUID
    ) -> Optional[CollaborationParticipant]:
        """The row for one employee on one resource, or ``None``."""
        stmt = select(CollaborationParticipant).where(
            CollaborationParticipant.resource_type == resource_type,
            CollaborationParticipant.resource_id == resource_id,
            CollaborationParticipant.employee_id == employee_id,
        )
        return self.session.scalars(stmt).first()

    def list_for_user(
        self, user_id: uuid.UUID
    ) -> Sequence[CollaborationParticipant]:
        """Every resource this user participates in (across all resource types)."""
        stmt = select(CollaborationParticipant).where(
            CollaborationParticipant.user_id == user_id
        )
        return self.session.scalars(stmt).all()

    # --- Writes ----------------------------------------------------------

    def add(
        self, participant: CollaborationParticipant
    ) -> CollaborationParticipant:
        """Persist a new participant and flush so it gets its id/defaults."""
        self.session.add(participant)
        self.session.flush()
        return participant

    def delete(self, participant: CollaborationParticipant) -> None:
        """Remove a participant row (the service commits)."""
        self.session.delete(participant)
        self.session.flush()
