"""Recovery engine package (Sprint 16.8 — advanced recovery & resilience).

Upgrades the recovery abstraction into a production-grade engine that decides *how*
failed workflows recover, while execution stays ``RecoveryCoordinator ->
WorkflowLifecycleManager -> WorkflowCoordinator`` (it executes no workflow or
capability itself). All retry timing is a deterministic caller-supplied integer
*tick* — no wall-clock, timer, thread, or async loop. It follows the flow
``RecoveryManager -> {RecoveryPolicy, RetryStrategy, RecoveryCoordinator,
FailureClassifier}``:

* the immutable DTOs :class:`RecoveryRequest`, :class:`RecoveryResult`,
  :class:`RecoveryHistory`, :class:`FailureInfo`, and
  :class:`RecoveryPolicyResult`, plus the :class:`FailureType` and
  :class:`RetryStrategyType` enums;
* the :class:`FailureClassifier` abstraction with :class:`RuleBasedFailureClassifier`;
* the :class:`RecoveryPolicy` abstraction with :class:`ImmediateRetryPolicy`,
  :class:`LimitedRetryPolicy`, and :class:`ManualRecoveryPolicy`;
* the deterministic :class:`RetryStrategy` (IMMEDIATE/DELAYED/EXPONENTIAL_BACKOFF/
  FIXED_INTERVAL);
* the :class:`RecoveryCoordinator` (delegates execution to the lifecycle manager,
  never the coordinator); and
* the :class:`RecoveryManager` engine.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.7, and it imports no capability module, no Workflow Coordinator, and no
timer/threading/async facility.
"""

from app.services.ai_employee.recovery.classifier import (
    FailureClassifier,
    RuleBasedFailureClassifier,
)
from app.services.ai_employee.recovery.coordinator import RecoveryCoordinator
from app.services.ai_employee.recovery.manager import RecoveryManager
from app.services.ai_employee.recovery.models import (
    FailureInfo,
    FailureType,
    RecoveryHistory,
    RecoveryHistoryEntry,
    RecoveryPolicyResult,
    RecoveryRequest,
    RecoveryResult,
    RetryStrategyType,
)
from app.services.ai_employee.recovery.policy import (
    ImmediateRetryPolicy,
    LimitedRetryPolicy,
    ManualRecoveryPolicy,
    RecoveryPolicy,
)
from app.services.ai_employee.recovery.strategy import RetryStrategy

__all__ = [
    # DTOs & enums
    "RecoveryRequest",
    "RecoveryResult",
    "RecoveryHistory",
    "RecoveryHistoryEntry",
    "FailureInfo",
    "RecoveryPolicyResult",
    "FailureType",
    "RetryStrategyType",
    # classifier / policy / strategy / coordinator / manager
    "FailureClassifier",
    "RuleBasedFailureClassifier",
    "RecoveryPolicy",
    "ImmediateRetryPolicy",
    "LimitedRetryPolicy",
    "ManualRecoveryPolicy",
    "RetryStrategy",
    "RecoveryCoordinator",
    "RecoveryManager",
]
