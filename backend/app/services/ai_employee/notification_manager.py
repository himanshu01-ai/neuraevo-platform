"""Notification manager (Sprint 16.2 — notification abstraction + in-memory store).

Defines the :class:`NotificationManager` abstraction and its basic implementation
:class:`InMemoryNotificationManager`. The abstraction lets later Sprint 16.x
implementations (push, email, webhook) plug in behind ``record``/``notifications``
without any change to the lifecycle manager. The basic implementation *stores*
notifications in an in-memory list — it never delivers them.

The four supported events (``workflow_started``, ``workflow_completed``,
``workflow_failed``, ``approval_required``) are exposed as convenience methods on
the abstraction, each producing an immutable :class:`WorkflowNotification` with a
deterministic per-instance sequence and id. Delivery — push, email, voice, mobile
— belongs to a later Sprint 16.x and is explicitly out of scope here. Strictly
additive to Sprints 1.x–16.1.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.services.ai_employee.platform_models import (
    WorkflowInstance,
    WorkflowNotification,
    WorkflowNotificationEvent,
)


class NotificationManager(ABC):
    """Abstraction for recording job notifications (stored only — never delivered).

    Implementations record a :class:`WorkflowNotification` per event and expose
    the stored notifications; the four milestone helpers
    (``workflow_started``/``workflow_completed``/``workflow_failed``/
    ``approval_required``) are provided on the abstraction and delegate to
    ``record``. Implementations must be deterministic and must not push, email, or
    otherwise deliver a notification.
    """

    @abstractmethod
    def record(
        self,
        instance_id: str,
        event: WorkflowNotificationEvent,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowNotification:
        """Record and return a :class:`WorkflowNotification` for ``event``."""

    @abstractmethod
    def notifications(
        self, instance_id: Optional[str] = None
    ) -> List[WorkflowNotification]:
        """Return the stored notifications (all, or for one ``instance_id``)."""

    # --- milestone helpers (the four supported events) -------------------
    def workflow_started(
        self, instance: WorkflowInstance
    ) -> WorkflowNotification:
        """Record a ``workflow_started`` notification for ``instance``."""
        return self.record(
            instance.instance_id,
            WorkflowNotificationEvent.WORKFLOW_STARTED,
            f"Workflow {instance.instance_id} started",
        )

    def workflow_completed(
        self, instance: WorkflowInstance
    ) -> WorkflowNotification:
        """Record a ``workflow_completed`` notification for ``instance``."""
        return self.record(
            instance.instance_id,
            WorkflowNotificationEvent.WORKFLOW_COMPLETED,
            f"Workflow {instance.instance_id} completed",
        )

    def workflow_failed(
        self, instance: WorkflowInstance
    ) -> WorkflowNotification:
        """Record a ``workflow_failed`` notification for ``instance``."""
        return self.record(
            instance.instance_id,
            WorkflowNotificationEvent.WORKFLOW_FAILED,
            f"Workflow {instance.instance_id} failed",
        )

    def approval_required(
        self, instance: WorkflowInstance
    ) -> WorkflowNotification:
        """Record an ``approval_required`` notification for ``instance``."""
        return self.record(
            instance.instance_id,
            WorkflowNotificationEvent.APPROVAL_REQUIRED,
            f"Workflow {instance.instance_id} requires approval",
        )


class InMemoryNotificationManager(NotificationManager):
    """Basic notification store — keeps notifications in memory, delivers none.

    Holds a per-instance list of :class:`WorkflowNotification` records (instance
    state, never a module-level global, so it is not a singleton). Each ``record``
    assigns the deterministic next per-instance sequence and a matching id, so a
    given sequence of calls always yields the same notifications. It stores only —
    no push, email, voice, or mobile delivery.
    """

    def __init__(self) -> None:
        self._by_instance: Dict[str, List[WorkflowNotification]] = {}

    def record(
        self,
        instance_id: str,
        event: WorkflowNotificationEvent,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowNotification:
        """Store and return a deterministic notification for ``event``."""
        existing = self._by_instance.setdefault(instance_id, [])
        sequence = len(existing)
        notification = WorkflowNotification(
            notification_id=f"notification-{instance_id}-{sequence}",
            workflow_instance_id=instance_id,
            event=event,
            message=message,
            sequence=sequence,
            notification_metadata=dict(metadata or {}),
        )
        existing.append(notification)
        return notification

    def notifications(
        self, instance_id: Optional[str] = None
    ) -> List[WorkflowNotification]:
        """Return a copy of the stored notifications (all, or for one instance)."""
        if instance_id is None:
            return [
                notification
                for records in self._by_instance.values()
                for notification in records
            ]
        return list(self._by_instance.get(instance_id, []))
