"""Notification emitter — the write seam for the inbox (Sprint 20D).

A small component the collaboration and sharing services hold to *raise* a
notification, kept separate from :class:`NotificationService` (which reads and
mutates) so a service can notify a user without pulling in the read/permission
machinery. It is the reusable event sink the sprint calls for: future providers
(email, push) plug in behind this one call.

Emitting is best-effort — a failure to notify must never break the action that
happened — so :meth:`emit` swallows and logs rather than raising. A resource
type maps 1:1 to a notification type through :data:`_TYPE_BY_RESOURCE`, so a
caller names the resource and the inbox category follows.
"""

import uuid
from typing import Optional

from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository
from app.utils.constants import (
    ActivityActorType,
    CollaborationResourceType,
    EmployeePriority,
    NotificationType,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

#: A collaborated resource maps straight onto its inbox category.
_TYPE_BY_RESOURCE = {
    CollaborationResourceType.TASK: NotificationType.TASK,
    CollaborationResourceType.WORKFLOW: NotificationType.WORKFLOW,
    CollaborationResourceType.MEMORY: NotificationType.MEMORY,
    CollaborationResourceType.CONVERSATION: NotificationType.CONVERSATION,
}


class NotificationEmitter:
    """Raises notifications for recipients (best-effort)."""

    def __init__(self, session) -> None:
        self.session = session
        self.notifications = NotificationRepository(session)

    @staticmethod
    def type_for(resource_type: CollaborationResourceType) -> NotificationType:
        """The inbox category for a collaborated resource."""
        return _TYPE_BY_RESOURCE[resource_type]

    def emit(
        self,
        recipient_user_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        description: str,
        *,
        resource_type: Optional[CollaborationResourceType] = None,
        resource_id: Optional[uuid.UUID] = None,
        actor_type: Optional[ActivityActorType] = None,
        actor_id: Optional[uuid.UUID] = None,
        priority: EmployeePriority = EmployeePriority.MEDIUM,
        commit: bool = True,
    ) -> Optional[Notification]:
        """Raise one notification. Never raises to its caller."""
        try:
            notification = Notification(
                user_id=recipient_user_id,
                type=notification_type.value,
                title=title,
                description=description,
                resource_type=(
                    resource_type.value if resource_type is not None else None
                ),
                resource_id=resource_id,
                actor_type=(actor_type.value if actor_type is not None else None),
                actor_id=actor_id,
                priority=priority.value,
            )
            self.notifications.add(notification)
            if commit:
                self.session.commit()
            return notification
        except Exception:  # pragma: no cover - defensive; notifying is best-effort
            logger.exception(
                "Failed to emit %s notification to %s",
                notification_type.value,
                recipient_user_id,
            )
            return None
