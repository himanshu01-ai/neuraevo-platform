"""SQLAlchemy ORM model for collaboration share links (Sprint 20B).

A share is a secure, redeemable link that grants participation in a resource.
It is the same polymorphic-resource idea as
:class:`~app.models.collaboration_participant.CollaborationParticipant`:
``resource_type`` + ``resource_id`` name any collaborated resource, with no
foreign key to the four frozen owning tables.

Only the *hash* of the token is stored, never the token itself — the same
stance the ``User`` model takes with its verification and reset tokens. The raw
token is returned once, at creation, and is unrecoverable afterward; redeeming
hashes the presented token and looks the row up by that digest.

A link is redeemable while it is neither revoked nor expired. Revocation is a
timestamp rather than a delete, so a link's history (who created it, when it was
withdrawn) survives for the activity timeline.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
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
from app.utils.constants import CollaborationRole

if TYPE_CHECKING:
    from app.models.user import User


class CollaborationShare(Base):
    """One secure share link for one resource.

    ``resource_type`` and ``role`` are plain strings validated at the schema and
    service layers, matching every other status/kind column. ``role`` is the
    role a redeemer is granted — ``editor`` or ``viewer``, never ``owner`` —
    enforced where the share is created.
    """

    __tablename__ = "collaboration_shares"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_collab_share_token"),
        Index("ix_collab_share_resource", "resource_type", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    #: SHA-256 hex digest of the share token. The token itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    role: Mapped[str] = mapped_column(
        String(50), default=CollaborationRole.VIEWER.value, nullable=False
    )

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    #: ``None`` means the link never expires. Otherwise it is redeemable only
    #: before this instant.
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Set when the owner withdraws the link. ``None`` means still live.
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    #: Identity-only. ``User`` is not taught about sharing, so it stays unchanged.
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])

    def is_active(self, now: datetime) -> bool:
        """A link is redeemable while neither revoked nor past its expiry."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return True

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<CollaborationShare resource={self.resource_type}:{self.resource_id} "
            f"role={self.role!r} revoked={self.revoked_at is not None}>"
        )
