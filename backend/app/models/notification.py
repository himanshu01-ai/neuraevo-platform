"""SQLAlchemy ORM model for user notifications (Sprint 20D).

One notification delivered to one user. It is the persistent backing for the
collaboration inbox: something happened that a user should know about — they
were added to a resource, someone joined one they own — and this row carries it
until the user reads, archives, or acts on it.

Like the timeline it is keyed by an optional polymorphic resource reference
(``resource_type`` + ``resource_id``) and an optional actor, with no foreign key
to either, so it serves every domain and survives the referenced record. Unlike
the timeline it is *mutable state*, not an audit log: the read/archived/pinned/
bookmarked/following/muted flags are exactly the quick actions the frontend
notification center offers.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.constants import EmployeePriority, NotificationType

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    """One notification for one recipient.

    ``type`` and ``priority`` are plain strings validated where notifications are
    created; ``priority`` reuses the platform's one
    :class:`~app.utils.constants.EmployeePriority` scale rather than minting a
    second low/medium/high/urgent vocabulary.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # The inbox reads one user's notifications, newest first.
        Index("ix_notification_recipient", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    #: The recipient. Cascades with the user.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    #: The record this notification is about. Polymorphic, no foreign key.
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)

    #: Who caused it. ``None`` for system notices.
    actor_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)

    priority: Mapped[str] = mapped_column(
        String(50), default=EmployeePriority.MEDIUM.value, nullable=False
    )

    # --- Mutable collaboration state (the quick actions) -----------------
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    following: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    #: Identity-only. ``User`` is not taught about notifications.
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Notification user_id={self.user_id} type={self.type!r} "
            f"read={self.read}>"
        )
