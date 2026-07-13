"""Notification Engine package (Sprint 16.4 — production-grade notifications).

Upgrades the Sprint 16.2 NotificationManager abstraction additively into a
production-grade, provider-independent Notification Engine that manages
notification *lifecycle* only and delivers nothing externally. It follows the flow
``NotificationManager -> NotificationPolicy -> NotificationQueue ->
NotificationDispatcher -> NotificationHistory``:

* the immutable DTOs :class:`NotificationMessage`, :class:`NotificationQueueItem`,
  :class:`NotificationHistoryEntry`, and :class:`NotificationPolicyResult`, plus
  the :class:`NotificationEvent`, :class:`NotificationPriority`, and
  :class:`NotificationStatus` enums;
* the configurable :class:`PriorityModel` (event -> priority);
* the :class:`NotificationPolicy` abstraction with
  :class:`ImmediateNotificationPolicy` and :class:`BatchedNotificationPolicy`;
* the deterministic in-memory priority :class:`NotificationQueue`;
* the :class:`NotificationDispatcher` abstraction with the in-memory
  :class:`InMemoryNotificationDispatcher` (no external delivery);
* the deterministic :class:`NotificationHistory` store; and
* the :class:`NotificationManager` engine plus the
  :class:`NotificationWorkflowCoordinator` integration that records notifications
  from the frozen Sprint 16.2 :class:`WorkflowLifecycleManager` transitions.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.3, and it imports no capability module.
"""

from app.services.ai_employee.notification.coordinator import (
    NotificationWorkflowCoordinator,
)
from app.services.ai_employee.notification.dispatcher import (
    InMemoryNotificationDispatcher,
    NotificationDispatcher,
)
from app.services.ai_employee.notification.history import NotificationHistory
from app.services.ai_employee.notification.manager import NotificationManager
from app.services.ai_employee.notification.models import (
    NotificationEvent,
    NotificationHistoryEntry,
    NotificationMessage,
    NotificationPolicyResult,
    NotificationPriority,
    NotificationQueueItem,
    NotificationStatus,
    PRIORITY_ORDER,
)
from app.services.ai_employee.notification.policies import (
    BatchedNotificationPolicy,
    ImmediateNotificationPolicy,
    NotificationPolicy,
)
from app.services.ai_employee.notification.priority import (
    DEFAULT_EVENT_PRIORITY,
    PriorityModel,
)
from app.services.ai_employee.notification.queue import NotificationQueue

__all__ = [
    # DTOs & enums
    "NotificationMessage",
    "NotificationQueueItem",
    "NotificationHistoryEntry",
    "NotificationPolicyResult",
    "NotificationEvent",
    "NotificationPriority",
    "NotificationStatus",
    "PRIORITY_ORDER",
    # priority model
    "PriorityModel",
    "DEFAULT_EVENT_PRIORITY",
    # policies
    "NotificationPolicy",
    "ImmediateNotificationPolicy",
    "BatchedNotificationPolicy",
    # queue + dispatcher + history + engine + integration
    "NotificationQueue",
    "NotificationDispatcher",
    "InMemoryNotificationDispatcher",
    "NotificationHistory",
    "NotificationManager",
    "NotificationWorkflowCoordinator",
]
