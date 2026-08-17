"""Notification priority model (Sprint 16.4 — configurable event → priority).

Defines :class:`PriorityModel`, the deterministic, *configurable* component that
assigns a :class:`NotificationPriority` to a :class:`NotificationEvent`. It ships
a default mapping (failures are ``CRITICAL``; cancellations, rejections, required
approvals, and recovery starts are ``HIGH``; most milestones are ``NORMAL``;
pauses are ``LOW``) and lets a caller override or extend the mapping and the
fallback priority at construction — priority is never hard-coded.

It holds no workflow state, executes nothing, and is deterministic: the same event
always maps to the same priority. Strictly additive to Sprints 1.x–16.3.
"""

from typing import Dict, Optional

from app.services.ai_employee.notification.models import (
    NotificationEvent,
    NotificationPriority,
)

# The default, override-able event → priority mapping. A caller may replace or
# extend it via :class:`PriorityModel`'s constructor, so priority stays
# configurable rather than hard-coded.
DEFAULT_EVENT_PRIORITY: Dict[NotificationEvent, NotificationPriority] = {
    NotificationEvent.WORKFLOW_STARTED: NotificationPriority.NORMAL,
    NotificationEvent.WORKFLOW_COMPLETED: NotificationPriority.NORMAL,
    NotificationEvent.WORKFLOW_FAILED: NotificationPriority.CRITICAL,
    NotificationEvent.WORKFLOW_PAUSED: NotificationPriority.LOW,
    NotificationEvent.WORKFLOW_RESUMED: NotificationPriority.NORMAL,
    NotificationEvent.WORKFLOW_CANCELLED: NotificationPriority.HIGH,
    NotificationEvent.APPROVAL_REQUIRED: NotificationPriority.HIGH,
    NotificationEvent.APPROVAL_APPROVED: NotificationPriority.NORMAL,
    NotificationEvent.APPROVAL_REJECTED: NotificationPriority.HIGH,
    NotificationEvent.RECOVERY_STARTED: NotificationPriority.HIGH,
    NotificationEvent.RECOVERY_COMPLETED: NotificationPriority.NORMAL,
}


class PriorityModel:
    """Assigns the deterministic priority of a notification event (configurable).

    Constructed with an optional ``event_priority`` override map (merged over the
    default mapping) and an optional ``default_priority`` fallback for unmapped
    events (defaults to ``NORMAL``). Stateless beyond its immutable mapping;
    ``priority`` is a pure lookup that executes nothing. Swapping the whole priority
    policy is a construction-time change with no impact on the policies, queue, or
    engine.
    """

    def __init__(
        self,
        event_priority: Optional[
            Dict[NotificationEvent, NotificationPriority]
        ] = None,
        default_priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> None:
        self._event_priority: Dict[NotificationEvent, NotificationPriority] = {
            **DEFAULT_EVENT_PRIORITY,
            **(event_priority or {}),
        }
        self._default_priority = default_priority

    def priority(self, event: NotificationEvent) -> NotificationPriority:
        """Return the priority of ``event`` (fallback for unmapped events)."""
        return self._event_priority.get(event, self._default_priority)
