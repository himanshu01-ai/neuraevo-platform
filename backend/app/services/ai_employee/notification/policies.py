"""Notification policies (Sprint 16.4 — policy abstraction + two implementations).

Defines the :class:`NotificationPolicy` abstraction and two implementations that
*decide when queued notifications become dispatchable*:

* :class:`ImmediateNotificationPolicy` — every queued notification is immediately
  dispatchable (dispatch as they arrive).
* :class:`BatchedNotificationPolicy` — notifications accumulate until a configurable
  batch size is reached, then the whole batch becomes dispatchable.

Each policy is deterministic and stateless and returns an immutable
:class:`NotificationPolicyResult`. Policies decide *when* to dispatch — they
neither enqueue, dispatch, deliver, nor execute anything; the engine coordinates
those. Strictly additive to Sprints 1.x–16.3.
"""

from abc import ABC, abstractmethod

from app.services.ai_employee.notification.models import (
    NotificationPolicyResult,
)


class NotificationPolicy(ABC):
    """Abstraction that decides when queued notifications become dispatchable.

    An implementation reads the current pending count and returns a
    :class:`NotificationPolicyResult` — ``should_dispatch`` plus the ``batch_size``
    to release. Implementations must be deterministic and must not enqueue,
    dispatch, deliver, or execute anything; the engine acts on the result.
    """

    @abstractmethod
    def evaluate(self, pending_count: int) -> NotificationPolicyResult:
        """Return the :class:`NotificationPolicyResult` for ``pending_count``."""


class ImmediateNotificationPolicy(NotificationPolicy):
    """Policy that dispatches every queued notification immediately.

    Deterministic and stateless: ``evaluate`` returns ``should_dispatch=True``
    whenever anything is pending and releases all of it (``batch_size`` equals the
    pending count), so notifications flow the moment they are created.
    """

    _POLICY_NAME = "ImmediateNotificationPolicy"

    def evaluate(self, pending_count: int) -> NotificationPolicyResult:
        """Return a result releasing all pending notifications at once."""
        dispatch = pending_count > 0
        return NotificationPolicyResult(
            policy=self._POLICY_NAME,
            should_dispatch=dispatch,
            batch_size=pending_count if dispatch else 0,
            reason="immediate dispatch",
        )


class BatchedNotificationPolicy(NotificationPolicy):
    """Policy that dispatches only once a configurable batch size accumulates.

    Constructed with a ``batch_size`` (default 3). ``evaluate`` returns
    ``should_dispatch=True`` only when the pending count reaches the batch size,
    releasing exactly one batch; otherwise it holds. Deterministic and stateless;
    it decides only — it enqueues, dispatches, delivers, and executes nothing.
    """

    _POLICY_NAME = "BatchedNotificationPolicy"

    def __init__(self, batch_size: int = 3) -> None:
        self.batch_size = max(batch_size, 1)

    def evaluate(self, pending_count: int) -> NotificationPolicyResult:
        """Return a result releasing one batch once the threshold is reached."""
        ready = pending_count >= self.batch_size
        return NotificationPolicyResult(
            policy=self._POLICY_NAME,
            should_dispatch=ready,
            batch_size=self.batch_size if ready else 0,
            reason=(
                f"batch of {self.batch_size} ready"
                if ready
                else f"holding until {self.batch_size} pending"
            ),
        )
