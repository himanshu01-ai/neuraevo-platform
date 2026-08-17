"""Recovery policies (Sprint 16.8 — configurable recovery rules).

Defines the :class:`RecoveryPolicy` abstraction and its three implementations,
which decide *how* a failed workflow should recover from its classified failure:

* :class:`ImmediateRetryPolicy` — retry a retryable failure at once (unbounded).
* :class:`LimitedRetryPolicy` — retry a retryable failure up to a configurable
  attempt bound, then give up (abort).
* :class:`ManualRecoveryPolicy` — never auto-retry; always require a human step.

A failure classified ``PERMANENT`` or ``USER_ACTION`` is never auto-retried (it
requires manual handling); ``TRANSIENT``/``SYSTEM``/``UNKNOWN`` are retryable. Each
policy is deterministic and stateless and returns an immutable
:class:`RecoveryPolicyResult` — it retries, aborts, and executes nothing. Strictly
additive to Sprints 1.x–16.7.
"""

from abc import ABC, abstractmethod

from app.services.ai_employee.recovery.models import (
    FailureInfo,
    FailureType,
    RecoveryPolicyResult,
)

# Failure types that are never auto-retried (a human must decide).
_NON_RETRYABLE = frozenset({FailureType.PERMANENT, FailureType.USER_ACTION})


class RecoveryPolicy(ABC):
    """Abstraction that decides how to recover from a classified failure (no execution).

    An implementation returns a :class:`RecoveryPolicyResult` for a
    :class:`FailureInfo` and the current attempt — whether to retry, whether a human
    is required, and the retry bound. Implementations must be deterministic and must
    not retry, abort, or execute anything.
    """

    @abstractmethod
    def evaluate(
        self, failure: FailureInfo, attempt: int
    ) -> RecoveryPolicyResult:
        """Return the recovery decision for ``failure`` at ``attempt``."""


class ImmediateRetryPolicy(RecoveryPolicy):
    """Policy that retries a retryable failure immediately (unbounded).

    ``evaluate`` retries any ``TRANSIENT``/``SYSTEM``/``UNKNOWN`` failure and flags a
    ``PERMANENT``/``USER_ACTION`` failure for manual handling. Deterministic and
    stateless.
    """

    _POLICY_NAME = "ImmediateRetryPolicy"

    def evaluate(
        self, failure: FailureInfo, attempt: int
    ) -> RecoveryPolicyResult:
        """Return an immediate-retry decision (manual for non-retryable failures)."""
        retryable = failure.failure_type not in _NON_RETRYABLE
        return RecoveryPolicyResult(
            policy=self._POLICY_NAME,
            should_retry=retryable,
            requires_manual=not retryable,
            failure_type=failure.failure_type,
            reason=(
                "retry immediately"
                if retryable
                else f"{failure.failure_type.value} requires manual recovery"
            ),
        )


class LimitedRetryPolicy(RecoveryPolicy):
    """Policy that retries a retryable failure up to ``max_attempts``, then aborts.

    Constructed with a ``max_attempts`` bound (default 3). ``evaluate`` retries a
    retryable failure while ``attempt < max_attempts``, flags a non-retryable failure
    for manual handling, and otherwise (retries exhausted) declines both — the
    manager then aborts. Deterministic and stateless.
    """

    _POLICY_NAME = "LimitedRetryPolicy"

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max(max_attempts, 0)

    def evaluate(
        self, failure: FailureInfo, attempt: int
    ) -> RecoveryPolicyResult:
        """Return a bounded-retry decision (manual for non-retryable, abort when spent)."""
        if failure.failure_type in _NON_RETRYABLE:
            return RecoveryPolicyResult(
                policy=self._POLICY_NAME,
                should_retry=False,
                requires_manual=True,
                max_attempts=self.max_attempts,
                failure_type=failure.failure_type,
                reason=(
                    f"{failure.failure_type.value} requires manual recovery"
                ),
            )
        should_retry = attempt < self.max_attempts
        return RecoveryPolicyResult(
            policy=self._POLICY_NAME,
            should_retry=should_retry,
            requires_manual=False,
            max_attempts=self.max_attempts,
            failure_type=failure.failure_type,
            reason=(
                f"retry {attempt + 1} of {self.max_attempts}"
                if should_retry
                else f"retries exhausted after {self.max_attempts}"
            ),
        )


class ManualRecoveryPolicy(RecoveryPolicy):
    """Policy that never auto-retries — every failure requires a human step.

    ``evaluate`` always returns ``should_retry=False`` and ``requires_manual=True``.
    Deterministic and stateless.
    """

    _POLICY_NAME = "ManualRecoveryPolicy"

    def evaluate(
        self, failure: FailureInfo, attempt: int
    ) -> RecoveryPolicyResult:
        """Return a manual-recovery decision (never auto-retry)."""
        return RecoveryPolicyResult(
            policy=self._POLICY_NAME,
            should_retry=False,
            requires_manual=True,
            failure_type=failure.failure_type,
            reason="manual recovery required",
        )
