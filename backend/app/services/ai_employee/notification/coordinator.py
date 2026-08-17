"""Notification ↔ workflow integration (Sprint 16.4 — emit on lifecycle transitions).

Defines :class:`NotificationWorkflowCoordinator`, the additive integration that
emits notifications from workflow lifecycle transitions without touching either
frozen component. It uses the injected Sprint 16.2 :class:`WorkflowLifecycleManager`
(through its existing public ``start``/``pause``/``resume``/``cancel``/``complete``/
``fail`` transitions) and the Sprint 16.4 :class:`NotificationManager` engine to
realise the required behaviour:

    lifecycle transition  ->  NotificationManager creates a notification record
                          ->  dispatcher receives dispatchable notifications
                          ->  no external delivery

Each method applies the frozen lifecycle transition first, then records the mapped
:class:`NotificationEvent` via the engine, and returns the transitioned
:class:`WorkflowInstance`. It redesigns neither the :class:`WorkflowInstance` nor
the :class:`WorkflowLifecycleManager`; it executes no capability and delivers
nothing externally. Constructor injection only; stateless beyond its two
collaborators; deterministic. Strictly additive to Sprints 1.x–16.3.
"""

from typing import Optional

from app.services.ai_employee.notification.manager import NotificationManager
from app.services.ai_employee.notification.models import NotificationEvent
from app.services.ai_employee.platform_models import WorkflowInstance
from app.services.ai_employee.workflow_lifecycle_manager import (
    WorkflowLifecycleManager,
)
from app.services.runtime.workflow_models import WorkflowExecutionResult


class NotificationWorkflowCoordinator:
    """Emits notifications from lifecycle transitions (uses both, redesigns none).

    Constructed with an injected :class:`WorkflowLifecycleManager` and
    :class:`NotificationManager` (constructor injection; it instantiates neither).
    Each transition method drives the lifecycle manager's public transition and
    then records the mapped notification event via the engine. It holds no mutable
    state, executes no capability, and delivers nothing externally.
    """

    def __init__(
        self,
        lifecycle_manager: WorkflowLifecycleManager,
        notification_manager: NotificationManager,
    ) -> None:
        self.lifecycle_manager = lifecycle_manager
        self.notification_manager = notification_manager

    def start(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Start the job and record a ``WORKFLOW_STARTED`` notification."""
        started = self.lifecycle_manager.start(instance)
        self._notify(started, NotificationEvent.WORKFLOW_STARTED)
        return started

    def pause(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Pause the job and record a ``WORKFLOW_PAUSED`` notification."""
        paused = self.lifecycle_manager.pause(instance)
        self._notify(paused, NotificationEvent.WORKFLOW_PAUSED)
        return paused

    def resume(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Resume the job and record a ``WORKFLOW_RESUMED`` notification."""
        resumed = self.lifecycle_manager.resume(instance)
        self._notify(resumed, NotificationEvent.WORKFLOW_RESUMED)
        return resumed

    def cancel(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Cancel the job and record a ``WORKFLOW_CANCELLED`` notification."""
        cancelled = self.lifecycle_manager.cancel(instance)
        self._notify(cancelled, NotificationEvent.WORKFLOW_CANCELLED)
        return cancelled

    def complete(
        self, instance: WorkflowInstance, workflow_result: WorkflowExecutionResult
    ) -> WorkflowInstance:
        """Complete the job and record a ``WORKFLOW_COMPLETED`` notification."""
        completed = self.lifecycle_manager.complete(instance, workflow_result)
        self._notify(completed, NotificationEvent.WORKFLOW_COMPLETED)
        return completed

    def fail(
        self,
        instance: WorkflowInstance,
        workflow_result: Optional[WorkflowExecutionResult] = None,
    ) -> WorkflowInstance:
        """Fail the job and record a ``WORKFLOW_FAILED`` notification."""
        failed = self.lifecycle_manager.fail(instance, workflow_result)
        self._notify(failed, NotificationEvent.WORKFLOW_FAILED)
        return failed

    def _notify(
        self, instance: WorkflowInstance, event: NotificationEvent
    ) -> None:
        """Record ``event`` for ``instance`` via the notification engine."""
        self.notification_manager.notify(event, instance.instance_id)
