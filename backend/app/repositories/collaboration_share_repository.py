"""Persistence for collaboration share links (Sprint 20B).

CRUD-style accessors over :class:`CollaborationShare`. Persistence only: it runs
queries and flushes, and decides nothing about who may create, revoke, or redeem
a share — that is the sharing service's job. Lookups are by the token *hash*;
the raw token never reaches this layer.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.collaboration_share import CollaborationShare


class CollaborationShareRepository:
    """CRUD-style accessors for :class:`CollaborationShare` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Reads -----------------------------------------------------------

    def get_by_id(self, share_id: uuid.UUID) -> Optional[CollaborationShare]:
        return self.session.get(CollaborationShare, share_id)

    def get_by_token_hash(self, token_hash: str) -> Optional[CollaborationShare]:
        """The share whose token hashes to ``token_hash``, or ``None``."""
        stmt = select(CollaborationShare).where(
            CollaborationShare.token_hash == token_hash
        )
        return self.session.scalars(stmt).first()

    def list_for_resource(
        self, resource_type: str, resource_id: uuid.UUID
    ) -> Sequence[CollaborationShare]:
        """Every share of one resource, newest first."""
        stmt = (
            select(CollaborationShare)
            .where(
                CollaborationShare.resource_type == resource_type,
                CollaborationShare.resource_id == resource_id,
            )
            .order_by(CollaborationShare.created_at.desc())
        )
        return self.session.scalars(stmt).all()

    # --- Writes ----------------------------------------------------------

    def add(self, share: CollaborationShare) -> CollaborationShare:
        """Persist a new share and flush so it gets its id/defaults."""
        self.session.add(share)
        self.session.flush()
        return share
