"""Persistence for user notifications (Sprint 20D).

CRUD-style accessors over :class:`Notification`. Persistence only: it queries and
flushes, and decides nothing about who may read or mutate a notification — the
notification service enforces ownership. The counts are computed here as plain
aggregates; what they *mean* for the UI is the service's concern.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    """CRUD-style accessors for :class:`Notification` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Writes ----------------------------------------------------------

    def add(self, notification: Notification) -> Notification:
        """Persist a new notification and flush so it gets its id/defaults."""
        self.session.add(notification)
        self.session.flush()
        return notification

    # --- Reads -----------------------------------------------------------

    def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        return self.session.get(Notification, notification_id)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        include_archived: bool = False,
        limit: int = 100,
    ) -> Sequence[Notification]:
        """One user's notifications, newest first."""
        stmt = select(Notification).where(Notification.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(Notification.archived.is_(False))
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        return self.session.scalars(stmt).all()

    def list_unread(self, user_id: uuid.UUID) -> Sequence[Notification]:
        """Every live unread notification, for the mark-all-read sweep."""
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.read.is_(False),
            Notification.archived.is_(False),
        )
        return self.session.scalars(stmt).all()

    # --- Aggregates ------------------------------------------------------

    def count_unread(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.read.is_(False),
            Notification.archived.is_(False),
        )
        return self.session.scalar(stmt) or 0

    def count_bookmarked(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.bookmarked.is_(True),
        )
        return self.session.scalar(stmt) or 0
