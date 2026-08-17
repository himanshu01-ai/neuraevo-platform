"""Unit + integration tests for the Sprint 16.8 Recovery engine.

Exercises the recovery subsystem: the configurable
:class:`RuleBasedFailureClassifier`, the :class:`RecoveryPolicy` implementations
(:class:`ImmediateRetryPolicy`, :class:`LimitedRetryPolicy`,
:class:`ManualRecoveryPolicy`), the deterministic :class:`RetryStrategy`, the
:class:`RecoveryCoordinator` (delegates to the frozen Sprint 16.2
:class:`WorkflowLifecycleManager`), and the :class:`RecoveryManager` that
coordinates them and integrates with the Sprint 16.5 persistence and Sprint 16.4
notification engines. All retry timing is a deterministic caller-supplied tick — no
wall-clock, timers, threads, or async loops.

Covers, as the sprint requires: failure classification, recovery policies, retry
strategies, immediate/limited retry, manual recovery, abort, history, persistence
integration, notification integration, execution delegation, DTO immutability, DI
wiring, and regression (Sprints 16.1–16.7 unchanged; the frozen planning/16.2
``RecoveryManager``s are distinct; the recovery sub-package imports no capability,
Workflow Coordinator, timer, thread, or async facility).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_recovery_engine
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    AutoApprovalPolicy,
    BasicRecoveryManager,
    EmployeeProfile,
    InMemoryNotificationManager,
    InMemoryPersistenceManager,
    ProgressTracker,
    TaskDelegation,
    WorkflowLifecycleManager,
    WorkflowLifecycleStatus,
)
import app.services.ai_employee.notification as ne
from app.services.ai_employee.persistence import (
    InMemoryPersistenceRepository,
    PersistenceManager,
)
from app.services.ai_employee.recovery import (
    FailureClassifier,
    FailureInfo,
    FailureType,
    ImmediateRetryPolicy,
    LimitedRetryPolicy,
    ManualRecoveryPolicy,
    RecoveryCoordinator,
    RecoveryHistory,
    RecoveryManager,
    RecoveryPolicy,
    RecoveryPolicyResult,
    RecoveryRequest,
    RecoveryResult,
    RetryStrategy,
    RetryStrategyType,
    RuleBasedFailureClassifier,
)
from app.services.runtime.artifact_coordinator import ArtifactCoordinator
from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionResult,
    CapabilityExecutionStatus,
)
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import WorkflowStep

_COMPLETED = CapabilityExecutionStatus.COMPLETED.value
_FAILED = CapabilityExecutionStatus.FAILED.value


# =====================================================================
# Offline capability double + helpers
# =====================================================================
class _Capability(ExecutionCapability):
    def __init__(self, status):
        self._status = status

    def execute(self, request):
        return CapabilityExecutionResult(
            runtime_id=request.runtime_id,
            execution_id=request.execution_id,
            execution_unit_id=request.execution_unit_id,
            capability_name=request.capability_name,
            execution_status=self._status,
            capability_outputs={},
            execution_metadata={},
        )


def _lifecycle(status=_COMPLETED):
    from app.core.dependencies import get_execution_orchestration_engine

    return WorkflowLifecycleManager(
        get_execution_orchestration_engine(),
        WorkflowCoordinator(
            CapabilityRouter({"demo": _Capability(status)}),
            ArtifactCoordinator(),
        ),
        ProgressTracker(),
        AutoApprovalPolicy(),
        InMemoryNotificationManager(),
        BasicRecoveryManager(),
        InMemoryPersistenceManager(),
    )


def _notification():
    return ne.NotificationManager(
        ne.ImmediateNotificationPolicy(),
        ne.NotificationQueue(),
        ne.InMemoryNotificationDispatcher(),
        ne.NotificationHistory(),
        ne.PriorityModel(),
    )


def _instance(task_id="t1", lifecycle=None):
    lifecycle = lifecycle or _lifecycle()
    return lifecycle.create_instance(
        EmployeeProfile(employee_id="e1", name="Ada"),
        TaskDelegation(task_id=task_id, task="do it"),
        [WorkflowStep(step_id="s1", capability_name="demo")],
    )


def _manager(policy=None, strategy=None, classifier=None, status=_COMPLETED):
    lifecycle = _lifecycle(status)
    return (
        RecoveryManager(
            policy or LimitedRetryPolicy(max_attempts=3),
            strategy or RetryStrategy(RetryStrategyType.IMMEDIATE),
            RecoveryCoordinator(lifecycle),
            classifier or RuleBasedFailureClassifier(),
            PersistenceManager(InMemoryPersistenceRepository()),
            _notification(),
        ),
        lifecycle,
    )


def _request(task_id="t1", lifecycle=None, reason="timeout occurred", attempt=0):
    lifecycle = lifecycle or _lifecycle()
    return RecoveryRequest(
        request_id=f"req-{task_id}",
        workflow_id=f"wf-{task_id}",
        instance=_instance(task_id, lifecycle),
        failure_reason=reason,
        attempt=attempt,
    )


def _failure(failure_type=FailureType.TRANSIENT, attempt=0):
    return FailureInfo(
        workflow_id="wf1", failure_type=failure_type, reason="r", attempt=attempt
    )


# =====================================================================
# Failure classification
# =====================================================================
class FailureClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = RuleBasedFailureClassifier()

    def test_is_a_failure_classifier(self):
        self.assertIsInstance(self.classifier, FailureClassifier)

    def test_transient(self):
        self.assertEqual(
            self.classifier.classify("connection timeout"),
            FailureType.TRANSIENT,
        )

    def test_permanent(self):
        self.assertEqual(
            self.classifier.classify("invalid argument"), FailureType.PERMANENT
        )

    def test_user_action(self):
        self.assertEqual(
            self.classifier.classify("awaiting approval"),
            FailureType.USER_ACTION,
        )

    def test_system(self):
        self.assertEqual(
            self.classifier.classify("internal error"), FailureType.SYSTEM
        )

    def test_unknown_default(self):
        self.assertEqual(
            self.classifier.classify("something odd"), FailureType.UNKNOWN
        )

    def test_configurable(self):
        classifier = RuleBasedFailureClassifier(
            rules={"boom": FailureType.SYSTEM},
            default_type=FailureType.PERMANENT,
        )
        self.assertEqual(classifier.classify("boom!"), FailureType.SYSTEM)
        self.assertEqual(
            classifier.classify("mystery"), FailureType.PERMANENT
        )


# =====================================================================
# Retry strategies
# =====================================================================
class RetryStrategyTests(unittest.TestCase):
    def test_immediate(self):
        strategy = RetryStrategy(RetryStrategyType.IMMEDIATE)
        self.assertEqual(strategy.next_retry(10, 3), 10)

    def test_delayed(self):
        strategy = RetryStrategy(RetryStrategyType.DELAYED, base_delay=5)
        self.assertEqual(strategy.next_retry(10, 3), 15)

    def test_fixed_interval(self):
        strategy = RetryStrategy(RetryStrategyType.FIXED_INTERVAL, base_delay=4)
        self.assertEqual(strategy.next_retry(10, 0), 14)
        self.assertEqual(strategy.next_retry(10, 5), 14)

    def test_exponential_backoff(self):
        strategy = RetryStrategy(
            RetryStrategyType.EXPONENTIAL_BACKOFF, base_delay=2
        )
        self.assertEqual(strategy.next_retry(10, 0), 12)
        self.assertEqual(strategy.next_retry(10, 1), 14)
        self.assertEqual(strategy.next_retry(10, 2), 18)

    def test_deterministic(self):
        strategy = RetryStrategy(RetryStrategyType.EXPONENTIAL_BACKOFF)
        self.assertEqual(strategy.next_retry(3, 2), strategy.next_retry(3, 2))


# =====================================================================
# Recovery policies
# =====================================================================
class RecoveryPolicyTests(unittest.TestCase):
    def test_policies_are_recovery_policies(self):
        for policy in (
            ImmediateRetryPolicy(),
            LimitedRetryPolicy(),
            ManualRecoveryPolicy(),
        ):
            self.assertIsInstance(policy, RecoveryPolicy)

    def test_immediate_retries_retryable(self):
        result = ImmediateRetryPolicy().evaluate(
            _failure(FailureType.TRANSIENT), 0
        )
        self.assertIsInstance(result, RecoveryPolicyResult)
        self.assertTrue(result.should_retry)
        self.assertFalse(result.requires_manual)

    def test_immediate_manual_for_permanent(self):
        result = ImmediateRetryPolicy().evaluate(
            _failure(FailureType.PERMANENT), 0
        )
        self.assertFalse(result.should_retry)
        self.assertTrue(result.requires_manual)

    def test_limited_retries_within_bound(self):
        policy = LimitedRetryPolicy(max_attempts=3)
        self.assertTrue(policy.evaluate(_failure(), 0).should_retry)
        self.assertTrue(policy.evaluate(_failure(), 2).should_retry)

    def test_limited_exhausted_aborts(self):
        policy = LimitedRetryPolicy(max_attempts=3)
        result = policy.evaluate(_failure(), 3)
        self.assertFalse(result.should_retry)
        self.assertFalse(result.requires_manual)  # -> abort

    def test_limited_manual_for_user_action(self):
        result = LimitedRetryPolicy().evaluate(
            _failure(FailureType.USER_ACTION), 0
        )
        self.assertFalse(result.should_retry)
        self.assertTrue(result.requires_manual)

    def test_manual_always_manual(self):
        result = ManualRecoveryPolicy().evaluate(_failure(), 0)
        self.assertFalse(result.should_retry)
        self.assertTrue(result.requires_manual)


# =====================================================================
# Classify (manager)
# =====================================================================
class ClassifyTests(unittest.TestCase):
    def test_classify_builds_failure_info(self):
        manager, lifecycle = _manager()
        failure = manager.classify(
            _request("t1", lifecycle, reason="rate limit exceeded", attempt=2)
        )
        self.assertIsInstance(failure, FailureInfo)
        self.assertEqual(failure.failure_type, FailureType.TRANSIENT)
        self.assertEqual(failure.attempt, 2)


# =====================================================================
# recover: immediate / limited retry
# =====================================================================
class RecoverRetryTests(unittest.TestCase):
    def test_immediate_retry_recovers_on_completion(self):
        manager, lifecycle = _manager(
            policy=ImmediateRetryPolicy(),
            strategy=RetryStrategy(RetryStrategyType.DELAYED, base_delay=3),
            status=_COMPLETED,
        )
        result = manager.recover(
            _request("t1", lifecycle, reason="timeout"), now_tick=10
        )
        self.assertEqual(result.action, "retry")
        self.assertTrue(result.recovered)
        self.assertEqual(result.final_status, "COMPLETED")
        self.assertEqual(result.next_retry_tick, 13)
        self.assertEqual(result.failure_type, FailureType.TRANSIENT)

    def test_retry_reports_unrecovered_on_failure(self):
        manager, lifecycle = _manager(
            policy=ImmediateRetryPolicy(), status=_FAILED
        )
        result = manager.recover(_request("t1", lifecycle, reason="timeout"))
        self.assertEqual(result.action, "retry")
        self.assertFalse(result.recovered)
        self.assertEqual(result.final_status, "FAILED")

    def test_limited_retry_within_bound(self):
        manager, lifecycle = _manager(
            policy=LimitedRetryPolicy(max_attempts=3), status=_COMPLETED
        )
        result = manager.recover(
            _request("t1", lifecycle, reason="timeout", attempt=1)
        )
        self.assertEqual(result.action, "retry")
        self.assertTrue(result.recovered)

    def test_force_retry(self):
        manager, lifecycle = _manager(status=_COMPLETED)
        result = manager.retry(_request("t1", lifecycle))
        self.assertEqual(result.action, "retry")
        self.assertEqual(result.policy, "forced-retry")


# =====================================================================
# recover: manual / abort
# =====================================================================
class RecoverManualAbortTests(unittest.TestCase):
    def test_manual_recovery_for_permanent(self):
        manager, lifecycle = _manager(policy=LimitedRetryPolicy())
        result = manager.recover(
            _request("t1", lifecycle, reason="invalid config")
        )
        self.assertEqual(result.action, "manual")
        self.assertTrue(result.requires_manual)
        self.assertIsNone(result.final_status)

    def test_manual_policy_always_manual(self):
        manager, lifecycle = _manager(policy=ManualRecoveryPolicy())
        result = manager.recover(_request("t1", lifecycle, reason="timeout"))
        self.assertEqual(result.action, "manual")

    def test_abort_when_retries_exhausted(self):
        manager, lifecycle = _manager(
            policy=LimitedRetryPolicy(max_attempts=2), status=_COMPLETED
        )
        result = manager.recover(
            _request("t1", lifecycle, reason="timeout", attempt=5)
        )
        self.assertEqual(result.action, "abort")
        self.assertEqual(result.final_status, "CANCELLED")

    def test_force_abort(self):
        manager, lifecycle = _manager()
        result = manager.abort(_request("t1", lifecycle))
        self.assertEqual(result.action, "abort")
        self.assertEqual(result.final_status, "CANCELLED")
        self.assertEqual(result.policy, "forced-abort")


# =====================================================================
# History
# =====================================================================
class HistoryTests(unittest.TestCase):
    def test_history_records_attempts(self):
        manager, lifecycle = _manager(status=_COMPLETED)
        manager.recover(_request("t1", lifecycle, reason="timeout"))
        manager.abort(_request("t2", lifecycle))
        history = manager.history()
        self.assertIsInstance(history, RecoveryHistory)
        self.assertEqual(history.total, 2)

    def test_history_filters_by_workflow(self):
        manager, lifecycle = _manager(status=_COMPLETED)
        manager.recover(_request("t1", lifecycle, reason="timeout"))
        manager.recover(_request("t2", lifecycle, reason="timeout"))
        self.assertEqual(manager.history("wf-t1").total, 1)
        self.assertEqual(manager.history("nope").total, 0)


# =====================================================================
# Execution delegation
# =====================================================================
class ExecutionDelegationTests(unittest.TestCase):
    def test_coordinator_only_holds_lifecycle_manager(self):
        lifecycle = _lifecycle()
        coordinator = RecoveryCoordinator(lifecycle)
        self.assertIs(coordinator.lifecycle_manager, lifecycle)
        self.assertEqual(set(vars(coordinator)), {"lifecycle_manager"})

    def test_execute_retry_delegates_and_runs(self):
        lifecycle = _lifecycle(_COMPLETED)
        coordinator = RecoveryCoordinator(lifecycle)
        executed = coordinator.execute_retry(_instance("t1", lifecycle))
        self.assertEqual(
            executed.lifecycle_state.status, WorkflowLifecycleStatus.COMPLETED
        )

    def test_abort_workflow_cancels(self):
        lifecycle = _lifecycle()
        coordinator = RecoveryCoordinator(lifecycle)
        aborted = coordinator.abort_workflow(_instance("t1", lifecycle))
        self.assertEqual(
            aborted.lifecycle_state.status, WorkflowLifecycleStatus.CANCELLED
        )

    def test_resume_workflow_resumes_paused(self):
        lifecycle = _lifecycle()
        coordinator = RecoveryCoordinator(lifecycle)
        paused = lifecycle.pause(lifecycle.start(_instance("t1", lifecycle)))
        resumed = coordinator.resume_workflow(paused)
        self.assertEqual(
            resumed.lifecycle_state.status, WorkflowLifecycleStatus.RUNNING
        )


# =====================================================================
# Persistence / notification integration
# =====================================================================
class IntegrationTests(unittest.TestCase):
    def test_retry_persists_the_executed_instance(self):
        manager, lifecycle = _manager(
            policy=ImmediateRetryPolicy(), status=_COMPLETED
        )
        request = _request("t1", lifecycle, reason="timeout")
        manager.recover(request)
        self.assertTrue(
            manager.persistence.exists(request.instance.instance_id)
        )

    def test_retry_records_recovery_notifications(self):
        manager, lifecycle = _manager(
            policy=ImmediateRetryPolicy(), status=_COMPLETED
        )
        manager.recover(_request("t1", lifecycle, reason="timeout"))
        events = [n.event for n in manager.notification_manager.dispatched()]
        self.assertIn(ne.NotificationEvent.RECOVERY_STARTED, events)
        self.assertIn(ne.NotificationEvent.RECOVERY_COMPLETED, events)

    def test_abort_records_cancelled_notification(self):
        manager, lifecycle = _manager()
        manager.abort(_request("t1", lifecycle))
        events = [n.event for n in manager.notification_manager.dispatched()]
        self.assertIn(ne.NotificationEvent.WORKFLOW_CANCELLED, events)


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.manager, self.lifecycle = _manager(status=_COMPLETED)
        self.request = _request("t1", self.lifecycle, reason="timeout")
        self.result = self.manager.recover(self.request)
        self.failure = self.manager.classify(self.request)

    def test_request_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.request.attempt = 9

    def test_result_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.result.recovered = False

    def test_failure_info_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.failure.failure_type = FailureType.PERMANENT

    def test_policy_result_is_frozen(self):
        result = LimitedRetryPolicy().evaluate(self.failure, 0)
        with self.assertRaises(ValidationError):
            result.should_retry = False

    def test_history_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.manager.history().total = 99


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_failure_classifier,
            get_recovery_coordinator,
            get_recovery_policy,
            get_retry_strategy,
        )

        self.assertIsInstance(
            get_failure_classifier(), RuleBasedFailureClassifier
        )
        self.assertIsInstance(get_recovery_policy(), LimitedRetryPolicy)
        self.assertIsInstance(get_retry_strategy(), RetryStrategy)
        self.assertIsInstance(
            get_recovery_coordinator(), RecoveryCoordinator
        )

    def test_engine_provider_wires_collaborators(self):
        from app.core.dependencies import get_recovery_engine

        engine = get_recovery_engine()
        self.assertIsInstance(engine, RecoveryManager)
        self.assertIsInstance(engine.policy, RecoveryPolicy)
        self.assertIsInstance(engine.strategy, RetryStrategy)
        self.assertIsInstance(engine.coordinator, RecoveryCoordinator)
        self.assertIsInstance(engine.classifier, FailureClassifier)
        self.assertIsInstance(engine.persistence, PersistenceManager)

    def test_engine_provider_uses_injected(self):
        from app.core.dependencies import get_recovery_engine

        policy = ManualRecoveryPolicy()
        engine = get_recovery_engine(policy=policy)
        self.assertIs(engine.policy, policy)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            FailureClassifierDep,
            RecoveryCoordinatorDep,
            RecoveryEngineDep,
            RecoveryPolicyDep,
            RetryStrategyDep,
        )

        for dep in (
            FailureClassifierDep,
            RecoveryPolicyDep,
            RetryStrategyDep,
            RecoveryCoordinatorDep,
            RecoveryEngineDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: prior sprints frozen; no forbidden imports
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_MODULES = {
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
        "workflow_coordinator",
        "threading",
        "asyncio",
        "time",
        "repository",
    }

    def test_frozen_planning_recovery_manager_is_distinct(self):
        from app.core.dependencies import get_recovery_manager
        from app.services.planning.recovery_manager import (
            RecoveryManager as PlanningRecoveryManager,
        )

        self.assertIsInstance(get_recovery_manager(), PlanningRecoveryManager)
        self.assertIsNot(PlanningRecoveryManager, RecoveryManager)

    def test_frozen_167_scheduler_unchanged(self):
        from app.core.dependencies import get_scheduler_manager
        import app.services.ai_employee.scheduler as scheduler_engine

        self.assertIsInstance(
            get_scheduler_manager(), scheduler_engine.SchedulerManager
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_recovery_package_imports_nothing_forbidden(self):
        import app.services.ai_employee.recovery as pkg

        package_dir = os.path.dirname(pkg.__file__)
        offenders = []
        for filename in os.listdir(package_dir):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(package_dir, filename)
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                elif isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                for name in names:
                    tail = name.rsplit(".", 1)[-1]
                    if tail in self._FORBIDDEN_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
