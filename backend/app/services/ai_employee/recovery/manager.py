"""Recovery engine (Sprint 16.8 — the production-grade RecoveryManager).

Defines :class:`RecoveryManager`, the coordinator of the Recovery engine. It
follows the locked flow ``RecoveryManager -> {RecoveryPolicy, RetryStrategy,
RecoveryCoordinator, FailureClassifier}`` (with the Sprint 16.5 Persistence and
Sprint 16.4 Notification engines as integrations) and decides *how* a failed
workflow recovers:

    classify   (FailureClassifier: what kind of failure?)
    recover    (RecoveryPolicy decides -> retry, manual, or abort)
    retry      (force a retry, delegated to the RecoveryCoordinator)
    abort      (force an abort, delegated to the RecoveryCoordinator)
    history    (the audit trail of recovery attempts)

It never executes a workflow or capability itself: it delegates every retry/abort
through the :class:`RecoveryCoordinator` (which delegates to the frozen
:class:`WorkflowLifecycleManager`), persists the recovered/aborted instance through
the Persistence Layer, and announces recovery through the notification engine. All
retry timing is a deterministic caller-supplied *tick* — no wall-clock, timer,
thread, or async loop. Constructor injection only; its only mutable state is a
deterministic sequence counter and the audit history. Strictly additive to Sprints
1.x–16.7, whose modules are left untouched.
"""

from typing import List, Optional

from app.services.ai_employee.notification.manager import NotificationManager
from app.services.ai_employee.notification.models import NotificationEvent
from app.services.ai_employee.persistence.manager import PersistenceManager
from app.services.ai_employee.platform_models import WorkflowLifecycleStatus
from app.services.ai_employee.recovery.classifier import FailureClassifier
from app.services.ai_employee.recovery.coordinator import RecoveryCoordinator
from app.services.ai_employee.recovery.models import (
    FailureInfo,
    RecoveryHistory,
    RecoveryHistoryEntry,
    RecoveryPolicyResult,
    RecoveryRequest,
    RecoveryResult,
)
from app.services.ai_employee.recovery.policy import RecoveryPolicy
from app.services.ai_employee.recovery.strategy import RetryStrategy

_COMPLETED = WorkflowLifecycleStatus.COMPLETED.value


class RecoveryManager:
    """Coordinates recovery over policy, strategy, coordinator, classifier, integrations.

    Constructed with an injected :class:`RecoveryPolicy`, :class:`RetryStrategy`,
    :class:`RecoveryCoordinator`, :class:`FailureClassifier`, Sprint 16.5
    :class:`PersistenceManager`, and Sprint 16.4 :class:`NotificationManager`
    (constructor injection; it instantiates none of them). It classifies failures,
    decides recovery via the policy, delegates every retry/abort through the
    coordinator, persists the result, and records an audit history. It executes no
    workflow or capability itself and holds a deterministic sequence counter plus the
    history only.
    """

    def __init__(
        self,
        policy: RecoveryPolicy,
        strategy: RetryStrategy,
        coordinator: RecoveryCoordinator,
        classifier: FailureClassifier,
        persistence: PersistenceManager,
        notification_manager: NotificationManager,
    ) -> None:
        self.policy = policy
        self.strategy = strategy
        self.coordinator = coordinator
        self.classifier = classifier
        self.persistence = persistence
        self.notification_manager = notification_manager
        self._sequence = 0
        self._history: List[RecoveryHistoryEntry] = []

    # --- classification --------------------------------------------------
    def classify(self, request: RecoveryRequest) -> FailureInfo:
        """Classify ``request``'s failure into an immutable :class:`FailureInfo`."""
        failure_type = self.classifier.classify(
            request.failure_reason, request.request_metadata
        )
        return FailureInfo(
            workflow_id=request.workflow_id,
            failure_type=failure_type,
            reason=request.failure_reason,
            attempt=request.attempt,
        )

    # --- coordinate recovery --------------------------------------------
    def recover(
        self, request: RecoveryRequest, now_tick: int = 0
    ) -> RecoveryResult:
        """Recover ``request`` per the policy and return the result (no direct execution).

        Classifies the failure, asks the policy, and then either retries (delegated
        to the coordinator), flags a manual recovery, or aborts (delegated to the
        coordinator). Records the attempt in the audit history. The manager decides
        *how* and delegates the running; it executes no workflow or capability
        itself.
        """
        failure = self.classify(request)
        decision = self.policy.evaluate(failure, request.attempt)
        if decision.should_retry:
            result = self._do_retry(request, failure, decision.policy, now_tick)
        elif decision.requires_manual:
            result = self._do_manual(request, failure, decision)
        else:
            result = self._do_abort(request, failure, decision.policy)
        self._record(request, result)
        return result

    def retry(
        self, request: RecoveryRequest, now_tick: int = 0
    ) -> RecoveryResult:
        """Force a retry of ``request`` (delegated to the coordinator) and record it."""
        failure = self.classify(request)
        result = self._do_retry(request, failure, "forced-retry", now_tick)
        self._record(request, result)
        return result

    def abort(self, request: RecoveryRequest) -> RecoveryResult:
        """Force an abort of ``request`` (delegated to the coordinator) and record it."""
        failure = self.classify(request)
        result = self._do_abort(request, failure, "forced-abort")
        self._record(request, result)
        return result

    def history(
        self, workflow_id: Optional[str] = None
    ) -> RecoveryHistory:
        """Return the recovery audit history (all, or for one ``workflow_id``)."""
        entries = (
            list(self._history)
            if workflow_id is None
            else [
                entry
                for entry in self._history
                if entry.request.workflow_id == workflow_id
            ]
        )
        return RecoveryHistory(entries=entries, total=len(entries))

    # --- action helpers --------------------------------------------------
    def _do_retry(
        self,
        request: RecoveryRequest,
        failure: FailureInfo,
        policy_name: str,
        now_tick: int,
    ) -> RecoveryResult:
        """Delegate a retry to the coordinator, persist, notify, and build the result."""
        next_retry_tick = self.strategy.next_retry(now_tick, request.attempt)
        self.notification_manager.notify(
            NotificationEvent.RECOVERY_STARTED, request.workflow_id
        )
        executed = self.coordinator.execute_retry(request.instance)
        self.persistence.save(executed)
        final_status = executed.lifecycle_state.status.value
        recovered = final_status == _COMPLETED
        if recovered:
            self.notification_manager.notify(
                NotificationEvent.RECOVERY_COMPLETED, request.workflow_id
            )
        return RecoveryResult(
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            action="retry",
            success=True,
            recovered=recovered,
            next_retry_tick=next_retry_tick,
            failure_type=failure.failure_type,
            policy=policy_name,
            final_status=final_status,
        )

    def _do_manual(
        self,
        request: RecoveryRequest,
        failure: FailureInfo,
        decision: RecoveryPolicyResult,
    ) -> RecoveryResult:
        """Record a manual recovery (no execution) and build the result."""
        self.notification_manager.notify(
            NotificationEvent.RECOVERY_STARTED, request.workflow_id
        )
        return RecoveryResult(
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            action="manual",
            success=True,
            recovered=False,
            requires_manual=True,
            failure_type=failure.failure_type,
            policy=decision.policy,
        )

    def _do_abort(
        self,
        request: RecoveryRequest,
        failure: FailureInfo,
        policy_name: str,
    ) -> RecoveryResult:
        """Delegate an abort to the coordinator, persist, notify, and build the result."""
        aborted = self.coordinator.abort_workflow(request.instance)
        self.persistence.save(aborted)
        self.notification_manager.notify(
            NotificationEvent.WORKFLOW_CANCELLED, request.workflow_id
        )
        return RecoveryResult(
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            action="abort",
            success=True,
            recovered=False,
            failure_type=failure.failure_type,
            policy=policy_name,
            final_status=aborted.lifecycle_state.status.value,
        )

    def _record(
        self, request: RecoveryRequest, result: RecoveryResult
    ) -> None:
        """Append a recovery history entry for ``request``/``result``."""
        self._sequence += 1
        self._history.append(
            RecoveryHistoryEntry(request=request, result=result)
        )
