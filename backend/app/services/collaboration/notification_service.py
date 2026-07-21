"""Notification service: the collaboration inbox (Sprint 20D).

Reads and mutates a user's own notifications and reports the header/badge
counts. Every operation is scoped to the authenticated user — a notification is
delivered to exactly one recipient, and only that recipient may read, act on, or
clear it — so a missing or someone-else's notification reads the same way: not
found.

Writing *new* notifications is not here — that is :class:`NotificationEmitter`,
which the collaboration and sharing services hold. This service owns the inbox
the recipient sees, never the events that fill it.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from app.models.notification import Notification
from app.models.user import User
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.collaboration import NotificationUpdate
from app.utils.constants import (
    ActivityActorType,
    EmployeePriority,
    NotificationType,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_LIMIT = 100


class NotificationError(Exception):
    """Base class for notification domain errors."""


class NotificationNotFoundError(NotificationError):
    """No such notification for this user."""


@dataclass(frozen=True)
class ResolvedNotification:
    """One notification with its actor's display name resolved."""

    id: uuid.UUID
    type: NotificationType
    title: str
    description: str
    resource_type: Optional[str]
    resource_id: Optional[uuid.UUID]
    actor_type: Optional[ActivityActorType]
    actor_id: Optional[uuid.UUID]
    actor_name: Optional[str]
    priority: EmployeePriority
    read: bool
    archived: bool
    pinned: bool
    bookmarked: bool
    following: bool
    muted: bool
    created_at: datetime


@dataclass(frozen=True)
class NotificationCounts:
    """The tallies the header and nav badges show."""

    unread: int
    mentions: int
    pending_approvals: int
    bookmarked: int


class NotificationService:
    """Reads, mutates, and counts one user's notifications."""

    def __init__(self, session) -> None:
        self.session = session
        self.notifications = NotificationRepository(session)
        self.users = UserRepository(session)
        self.employees = EmployeeRepository(session)

    # --- Reads -----------------------------------------------------------

    def list_for_user(
        self,
        user: User,
        *,
        include_archived: bool = False,
        limit: int = _MAX_LIMIT,
    ) -> List[ResolvedNotification]:
        rows = self.notifications.list_for_user(
            user.id,
            include_archived=include_archived,
            limit=self._bounded(limit),
        )
        return [self._resolve(row) for row in rows]

    def get(self, user: User, notification_id: uuid.UUID) -> ResolvedNotification:
        return self._resolve(self._require(user, notification_id))

    def counts(self, user: User) -> NotificationCounts:
        """Header/badge tallies. ``mentions`` and ``pending_approvals`` are 0
        until the comment and approval slices land — the shape is stable now so
        the frontend badge wiring need not change when they do."""
        return NotificationCounts(
            unread=self.notifications.count_unread(user.id),
            mentions=0,
            pending_approvals=0,
            bookmarked=self.notifications.count_bookmarked(user.id),
        )

    # --- Mutations -------------------------------------------------------

    def update(
        self, user: User, notification_id: uuid.UUID, data: NotificationUpdate
    ) -> ResolvedNotification:
        """Apply any subset of the quick-action flags. Only supplied fields change."""
        notification = self._require(user, notification_id)
        fields = data.model_dump(exclude_unset=True)
        for field, value in fields.items():
            setattr(notification, field, value)
            if field == "read":
                notification.read_at = (
                    datetime.now(timezone.utc) if value else None
                )
        self.session.commit()
        return self._resolve(notification)

    def mark_all_read(self, user: User) -> List[ResolvedNotification]:
        """Mark every live unread notification read, returning the inbox."""
        now = datetime.now(timezone.utc)
        for notification in self.notifications.list_unread(user.id):
            notification.read = True
            notification.read_at = now
        self.session.commit()
        return self.list_for_user(user)

    # --- Helpers ---------------------------------------------------------

    def _require(self, user: User, notification_id: uuid.UUID) -> Notification:
        notification = self.notifications.get_by_id(notification_id)
        if notification is None or notification.user_id != user.id:
            raise NotificationNotFoundError(str(notification_id))
        return notification

    def _resolve(self, row: Notification) -> ResolvedNotification:
        return ResolvedNotification(
            id=row.id,
            type=NotificationType(row.type),
            title=row.title,
            description=row.description,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            actor_type=(
                ActivityActorType(row.actor_type)
                if row.actor_type is not None
                else None
            ),
            actor_id=row.actor_id,
            actor_name=self._actor_name(row.actor_type, row.actor_id),
            priority=EmployeePriority(row.priority),
            read=row.read,
            archived=row.archived,
            pinned=row.pinned,
            bookmarked=row.bookmarked,
            following=row.following,
            muted=row.muted,
            created_at=row.created_at,
        )

    def _actor_name(
        self, actor_type: Optional[str], actor_id: Optional[uuid.UUID]
    ) -> Optional[str]:
        if actor_type is None or actor_id is None:
            return None
        if actor_type == ActivityActorType.EMPLOYEE.value:
            employee = self.employees.get_by_id(actor_id, include_deleted=True)
            return employee.name if employee is not None else "AI employee"
        if actor_type == ActivityActorType.SYSTEM.value:
            return "System"
        user = self.users.get_by_id(actor_id)
        if user is None:
            return "Unknown user"
        return user.full_name or user.email

    @staticmethod
    def _bounded(limit: int) -> int:
        return max(1, min(limit, _MAX_LIMIT))
