"""Unit + integration tests for the Sprint 16.3 Human Approval Engine.

Exercises the production-grade approval subsystem: the configurable
:class:`RiskModel`, the :class:`ApprovalPolicy` implementations
(:class:`AutoApprovalPolicy`, :class:`RiskBasedApprovalPolicy`), the deterministic
in-memory :class:`ApprovalQueueManager`, the :class:`ApprovalManager` engine (the
single approval entry point), and the :class:`ApprovalWorkflowCoordinator` that
pauses/resumes/cancels a job through the frozen Sprint 16.2
:class:`WorkflowLifecycleManager`. No network or SDK; everything is deterministic
and in-memory.

Covers, as the sprint requires: approval policies, risk evaluation, auto approval,
manual approval (approve/reject), pending, expired, queue operations, workflow
pause/resume/cancel, DTO immutability, DI wiring, and regression (Sprints
16.1/16.2 unchanged; the frozen approval abstraction still works; the approval
sub-package imports no capability module).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_approval_engine
"""

import ast
import os
import unittest

from pydantic import ValidationError

from app.services.ai_employee import (
    EmployeeProfile,
    TaskDelegation,
    WorkflowLifecycleStatus,
)
from app.services.ai_employee.approval import (
    ApprovalDecision,
    ApprovalDecisionStatus,
    ApprovalHistory,
    ApprovalManager,
    ApprovalPolicy,
    ApprovalPolicyResult,
    ApprovalQueue,
    ApprovalQueueManager,
    ApprovalRequest,
    ApprovalRiskLevel,
    ApprovalWorkflowCoordinator,
    ApprovalWorkflowOutcome,
    AutoApprovalPolicy,
    RiskBasedApprovalPolicy,
    RiskModel,
)
from app.services.runtime.workflow_models import WorkflowStep


# =====================================================================
# Helpers
# =====================================================================
def _request(
    action="send_email",
    risk=ApprovalRiskLevel.CRITICAL,
    workflow_id="wf1",
    step_id="s1",
):
    return ApprovalRequest(
        request_id=f"req-{workflow_id}-{step_id}",
        workflow_id=workflow_id,
        step_id=step_id,
        requested_action=action,
        risk_level=risk,
    )


def _engine(policy=None):
    return ApprovalManager(
        policy or RiskBasedApprovalPolicy(),
        RiskModel(),
        ApprovalQueueManager(),
    )


def _profile():
    return EmployeeProfile(employee_id="e1", name="Ada")


def _delegation(task_id="t1"):
    return TaskDelegation(task_id=task_id, task="do it")


def _steps():
    return [WorkflowStep(step_id="s1", capability_name="demo")]


def _coordinator(policy=None):
    from app.core.dependencies import get_workflow_lifecycle_manager

    return ApprovalWorkflowCoordinator(
        get_workflow_lifecycle_manager(), _engine(policy)
    )


# =====================================================================
# Risk evaluation (configurable risk model)
# =====================================================================
class RiskModelTests(unittest.TestCase):
    def setUp(self):
        self.model = RiskModel()

    def test_default_low_actions(self):
        for action in ("read_file", "search_email", "list_calendar"):
            self.assertEqual(self.model.assess(action), ApprovalRiskLevel.LOW)

    def test_default_medium_actions(self):
        for action in ("create_event", "draft_email", "git_branch"):
            self.assertEqual(self.model.assess(action), ApprovalRiskLevel.MEDIUM)

    def test_default_high_actions(self):
        for action in ("delete_files", "commit_code", "move_repositories"):
            self.assertEqual(self.model.assess(action), ApprovalRiskLevel.HIGH)

    def test_default_critical_actions(self):
        for action in ("send_email", "delete_repository", "payment"):
            self.assertEqual(
                self.model.assess(action), ApprovalRiskLevel.CRITICAL
            )

    def test_unknown_action_uses_default_fallback(self):
        self.assertEqual(
            self.model.assess("mystery_action"), ApprovalRiskLevel.MEDIUM
        )

    def test_configurable_overrides_and_fallback(self):
        model = RiskModel(
            action_risk={"read_file": ApprovalRiskLevel.HIGH},
            default_risk=ApprovalRiskLevel.CRITICAL,
        )
        self.assertEqual(model.assess("read_file"), ApprovalRiskLevel.HIGH)
        self.assertEqual(
            model.assess("unknown"), ApprovalRiskLevel.CRITICAL
        )

    def test_assess_is_deterministic(self):
        self.assertEqual(
            self.model.assess("send_email"), self.model.assess("send_email")
        )


# =====================================================================
# Approval policies
# =====================================================================
class ApprovalPolicyTests(unittest.TestCase):
    def test_auto_policy_never_requires_approval(self):
        policy = AutoApprovalPolicy()
        result = policy.evaluate(_request(risk=ApprovalRiskLevel.CRITICAL))
        self.assertIsInstance(result, ApprovalPolicyResult)
        self.assertFalse(result.requires_approval)
        self.assertEqual(result.auto_decision, ApprovalDecisionStatus.APPROVED)

    def test_auto_policy_is_an_approval_policy(self):
        self.assertIsInstance(AutoApprovalPolicy(), ApprovalPolicy)

    def test_risk_policy_requires_approval_at_or_above_threshold(self):
        policy = RiskBasedApprovalPolicy()  # threshold HIGH
        self.assertTrue(
            policy.evaluate(_request(risk=ApprovalRiskLevel.HIGH)).requires_approval
        )
        self.assertTrue(
            policy.evaluate(
                _request(risk=ApprovalRiskLevel.CRITICAL)
            ).requires_approval
        )

    def test_risk_policy_auto_approves_below_threshold(self):
        policy = RiskBasedApprovalPolicy()  # threshold HIGH
        for risk in (ApprovalRiskLevel.LOW, ApprovalRiskLevel.MEDIUM):
            result = policy.evaluate(_request(risk=risk))
            self.assertFalse(result.requires_approval)
            self.assertEqual(
                result.auto_decision, ApprovalDecisionStatus.APPROVED
            )

    def test_risk_policy_threshold_is_configurable(self):
        policy = RiskBasedApprovalPolicy(threshold=ApprovalRiskLevel.MEDIUM)
        self.assertTrue(
            policy.evaluate(
                _request(risk=ApprovalRiskLevel.MEDIUM)
            ).requires_approval
        )
        self.assertFalse(
            policy.evaluate(
                _request(risk=ApprovalRiskLevel.LOW)
            ).requires_approval
        )


# =====================================================================
# Engine: request creation & risk assessment
# =====================================================================
class EngineRequestTests(unittest.TestCase):
    def test_create_request_assesses_risk(self):
        engine = _engine()
        request = engine.create_request("wf1", "s1", "send_email", reason="r")
        self.assertEqual(request.risk_level, ApprovalRiskLevel.CRITICAL)
        self.assertEqual(request.requested_action, "send_email")
        self.assertEqual(request.workflow_id, "wf1")
        self.assertEqual(request.step_id, "s1")
        self.assertEqual(request.reason, "r")

    def test_request_ids_are_deterministic_and_sequenced(self):
        engine = _engine()
        first = engine.create_request("wf1", "s1", "read_file")
        second = engine.create_request("wf1", "s2", "read_file")
        self.assertEqual(first.request_id, "approval-wf1-s1-1")
        self.assertEqual(second.request_id, "approval-wf1-s2-2")
        self.assertEqual(first.created_at_sequence, 1)
        self.assertEqual(second.created_at_sequence, 2)

    def test_assess_risk_delegates_to_model(self):
        self.assertEqual(
            _engine().assess_risk("delete_files"), ApprovalRiskLevel.HIGH
        )

    def test_two_fresh_engines_agree(self):
        a = _engine().create_request("wf1", "s1", "send_email")
        b = _engine().create_request("wf1", "s1", "send_email")
        self.assertEqual(a, b)


# =====================================================================
# Engine: auto approval
# =====================================================================
class AutoApprovalTests(unittest.TestCase):
    def test_submit_auto_approves_low_risk(self):
        engine = _engine()  # risk-based, threshold HIGH
        request = engine.create_request("wf1", "s1", "read_file")
        decision = engine.submit(request)
        self.assertEqual(decision.decision, ApprovalDecisionStatus.APPROVED)
        self.assertEqual(decision.approver_id, "auto")
        self.assertEqual(engine.pending(), [])

    def test_submit_auto_approves_everything_under_auto_policy(self):
        engine = _engine(AutoApprovalPolicy())
        request = engine.create_request("wf1", "s1", "delete_repository")
        decision = engine.submit(request)
        self.assertEqual(decision.decision, ApprovalDecisionStatus.APPROVED)
        self.assertEqual(engine.pending(), [])


# =====================================================================
# Engine: manual approval (pending -> approve / reject / expire)
# =====================================================================
class ManualApprovalTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()  # risk-based, threshold HIGH
        self.request = self.engine.create_request("wf1", "s1", "send_email")
        self.pending_decision = self.engine.submit(self.request)

    def test_high_risk_submit_is_pending_and_enqueued(self):
        self.assertEqual(
            self.pending_decision.decision, ApprovalDecisionStatus.PENDING
        )
        self.assertIsNone(self.pending_decision.approver_id)
        self.assertEqual(
            [r.request_id for r in self.engine.pending()],
            [self.request.request_id],
        )

    def test_approve_records_decision_and_dequeues(self):
        decision = self.engine.approve(self.request, "mgr-1", reason="ok")
        self.assertEqual(decision.decision, ApprovalDecisionStatus.APPROVED)
        self.assertEqual(decision.approver_id, "mgr-1")
        self.assertEqual(decision.reason, "ok")
        self.assertEqual(self.engine.pending(), [])

    def test_reject_records_decision_and_dequeues(self):
        decision = self.engine.reject(self.request, "mgr-1")
        self.assertEqual(decision.decision, ApprovalDecisionStatus.REJECTED)
        self.assertEqual(decision.approver_id, "mgr-1")
        self.assertEqual(self.engine.pending(), [])

    def test_expire_records_decision_and_dequeues(self):
        decision = self.engine.expire(self.request)
        self.assertEqual(decision.decision, ApprovalDecisionStatus.EXPIRED)
        self.assertEqual(self.engine.pending(), [])

    def test_decision_sequence_is_deterministic(self):
        # request seq=1, PENDING decision seq=2, APPROVED decision seq=3
        approved = self.engine.approve(self.request, "mgr-1")
        self.assertEqual(self.request.created_at_sequence, 1)
        self.assertEqual(self.pending_decision.decided_at_sequence, 2)
        self.assertEqual(approved.decided_at_sequence, 3)

    def test_history_records_every_decision(self):
        self.engine.approve(self.request, "mgr-1")
        history = self.engine.history()
        self.assertIsInstance(history, ApprovalHistory)
        self.assertEqual(history.total, 2)  # PENDING + APPROVED
        statuses = [entry.decision.decision for entry in history.entries]
        self.assertEqual(
            statuses,
            [ApprovalDecisionStatus.PENDING, ApprovalDecisionStatus.APPROVED],
        )


# =====================================================================
# Queue operations
# =====================================================================
class ApprovalQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = ApprovalQueueManager()
        self.r1 = _request(workflow_id="wf1", step_id="s1")
        self.r2 = _request(workflow_id="wf2", step_id="s2")
        self.r3 = _request(workflow_id="wf1", step_id="s3")

    def test_enqueue_and_pending_preserve_order(self):
        for request in (self.r1, self.r2, self.r3):
            self.queue.enqueue(request)
        self.assertEqual(
            [r.request_id for r in self.queue.pending()],
            [self.r1.request_id, self.r2.request_id, self.r3.request_id],
        )

    def test_dequeue_fifo_head(self):
        self.queue.enqueue(self.r1)
        self.queue.enqueue(self.r2)
        self.assertEqual(self.queue.dequeue(), self.r1)
        self.assertEqual([r.request_id for r in self.queue.pending()], [self.r2.request_id])

    def test_dequeue_by_id(self):
        self.queue.enqueue(self.r1)
        self.queue.enqueue(self.r2)
        self.assertEqual(self.queue.dequeue(self.r2.request_id), self.r2)
        self.assertEqual(
            [r.request_id for r in self.queue.pending()], [self.r1.request_id]
        )

    def test_dequeue_missing_returns_none(self):
        self.assertIsNone(self.queue.dequeue())
        self.queue.enqueue(self.r1)
        self.assertIsNone(self.queue.dequeue("nope"))

    def test_find_by_workflow(self):
        for request in (self.r1, self.r2, self.r3):
            self.queue.enqueue(request)
        found = self.queue.find_by_workflow("wf1")
        self.assertEqual(
            [r.request_id for r in found], [self.r1.request_id, self.r3.request_id]
        )

    def test_snapshot_is_immutable_queue(self):
        self.queue.enqueue(self.r1)
        snapshot = self.queue.snapshot()
        self.assertIsInstance(snapshot, ApprovalQueue)
        self.assertEqual(snapshot.pending_count, 1)
        self.assertEqual(snapshot.total, 1)


# =====================================================================
# Workflow integration: pause / resume / cancel
# =====================================================================
class WorkflowIntegrationTests(unittest.TestCase):
    def _instance(self, coord, task_id="t1"):
        return coord.lifecycle_manager.create_instance(
            _profile(), _delegation(task_id), _steps()
        )

    def test_approval_required_pauses_workflow(self):
        coord = _coordinator()
        outcome = coord.request_approval(
            self._instance(coord), "s1", "delete_repository"
        )
        self.assertIsInstance(outcome, ApprovalWorkflowOutcome)
        self.assertEqual(
            outcome.instance.lifecycle_state.status,
            WorkflowLifecycleStatus.PAUSED,
        )
        self.assertEqual(
            outcome.decision.decision, ApprovalDecisionStatus.PENDING
        )
        self.assertEqual(len(coord.approval_manager.pending()), 1)

    def test_approve_resumes_workflow(self):
        coord = _coordinator()
        gated = coord.request_approval(
            self._instance(coord), "s1", "delete_repository"
        )
        resumed = coord.approve(gated.instance, gated.request, "mgr-1")
        self.assertEqual(
            resumed.instance.lifecycle_state.status,
            WorkflowLifecycleStatus.RUNNING,
        )
        self.assertEqual(
            resumed.decision.decision, ApprovalDecisionStatus.APPROVED
        )
        self.assertEqual(coord.approval_manager.pending(), [])

    def test_reject_cancels_workflow(self):
        coord = _coordinator()
        gated = coord.request_approval(
            self._instance(coord), "s1", "delete_repository"
        )
        rejected = coord.reject(gated.instance, gated.request, "mgr-1")
        self.assertEqual(
            rejected.instance.lifecycle_state.status,
            WorkflowLifecycleStatus.CANCELLED,
        )
        self.assertTrue(rejected.instance.lifecycle_state.is_terminal)
        self.assertEqual(
            rejected.decision.decision, ApprovalDecisionStatus.REJECTED
        )

    def test_auto_approved_action_does_not_pause(self):
        coord = _coordinator()  # risk-based, threshold HIGH
        outcome = coord.request_approval(self._instance(coord), "s1", "read_file")
        # low risk auto-approves; workflow started and left running (not paused)
        self.assertEqual(
            outcome.instance.lifecycle_state.status,
            WorkflowLifecycleStatus.RUNNING,
        )
        self.assertEqual(
            outcome.decision.decision, ApprovalDecisionStatus.APPROVED
        )

    def test_coordinator_delegates_and_holds_no_state(self):
        coord = _coordinator()
        self.assertEqual(
            set(vars(coord)), {"lifecycle_manager", "approval_manager"}
        )


# =====================================================================
# DTO immutability
# =====================================================================
class ImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        self.request = self.engine.create_request("wf1", "s1", "send_email")
        self.decision = self.engine.submit(self.request)

    def test_request_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.request.risk_level = ApprovalRiskLevel.LOW

    def test_decision_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.decision.decision = ApprovalDecisionStatus.APPROVED

    def test_queue_snapshot_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.engine.queue_snapshot().total = 99

    def test_history_is_frozen(self):
        with self.assertRaises(ValidationError):
            self.engine.history().total = 99

    def test_policy_result_is_frozen(self):
        result = RiskBasedApprovalPolicy().evaluate(self.request)
        with self.assertRaises(ValidationError):
            result.requires_approval = False

    def test_workflow_outcome_is_frozen(self):
        coord = _coordinator()
        instance = coord.lifecycle_manager.create_instance(
            _profile(), _delegation(), _steps()
        )
        outcome = coord.request_approval(instance, "s1", "send_email")
        with self.assertRaises(ValidationError):
            outcome.decision = None


# =====================================================================
# Dependency injection (composition root)
# =====================================================================
class DependencyInjectionTests(unittest.TestCase):
    def test_basic_providers(self):
        from app.core.dependencies import (
            get_approval_policy,
            get_approval_queue,
            get_approval_risk_model,
        )

        self.assertIsInstance(get_approval_risk_model(), RiskModel)
        self.assertIsInstance(get_approval_policy(), RiskBasedApprovalPolicy)
        self.assertIsInstance(get_approval_queue(), ApprovalQueueManager)

    def test_engine_provider_wires_collaborators(self):
        from app.core.dependencies import get_approval_engine

        engine = get_approval_engine()
        self.assertIsInstance(engine, ApprovalManager)
        self.assertIsInstance(engine.policy, ApprovalPolicy)
        self.assertIsInstance(engine.risk_model, RiskModel)
        self.assertIsInstance(engine.queue, ApprovalQueueManager)

    def test_engine_provider_uses_injected(self):
        from app.core.dependencies import get_approval_engine

        policy = AutoApprovalPolicy()
        engine = get_approval_engine(policy=policy)
        self.assertIs(engine.policy, policy)

    def test_coordinator_provider_wires_collaborators(self):
        from app.core.dependencies import get_approval_workflow_coordinator
        from app.services.ai_employee import WorkflowLifecycleManager

        coord = get_approval_workflow_coordinator()
        self.assertIsInstance(coord, ApprovalWorkflowCoordinator)
        self.assertIsInstance(
            coord.lifecycle_manager, WorkflowLifecycleManager
        )
        self.assertIsInstance(coord.approval_manager, ApprovalManager)

    def test_dep_aliases_exist(self):
        from app.core.dependencies import (
            ApprovalEngineDep,
            ApprovalPolicyDep,
            ApprovalQueueDep,
            ApprovalRiskModelDep,
            ApprovalWorkflowCoordinatorDep,
        )

        for dep in (
            ApprovalRiskModelDep,
            ApprovalPolicyDep,
            ApprovalQueueDep,
            ApprovalEngineDep,
            ApprovalWorkflowCoordinatorDep,
        ):
            self.assertIsNotNone(dep)


# =====================================================================
# Regression: Foundation / Platform frozen; frozen approval intact; no capability
# =====================================================================
class RegressionTests(unittest.TestCase):
    _FORBIDDEN_CAPABILITY_MODULES = {
        "browser_capability",
        "python_capability",
        "filesystem_capability",
        "email_capability",
        "calendar_capability",
        "github_capability",
    }

    def test_frozen_162_approval_manager_unchanged(self):
        # The frozen Sprint 16.2 ApprovalManager ABC + AutoApprovalPolicy still
        # exist and behave as before (distinct from the Sprint 16.3 engine).
        from app.core.dependencies import get_approval_manager
        from app.services.ai_employee import (
            ApprovalManager as FrozenApprovalManager,
        )
        from app.services.ai_employee import (
            AutoApprovalPolicy as FrozenAutoApprovalPolicy,
        )

        policy = get_approval_manager()
        self.assertIsInstance(policy, FrozenAutoApprovalPolicy)
        self.assertIsInstance(policy, FrozenApprovalManager)

    def test_frozen_162_lifecycle_manager_unchanged(self):
        from app.core.dependencies import get_workflow_lifecycle_manager
        from app.services.ai_employee import WorkflowLifecycleManager

        self.assertIsInstance(
            get_workflow_lifecycle_manager(), WorkflowLifecycleManager
        )

    def test_frozen_161_ai_employee_unchanged(self):
        from app.core.dependencies import get_ai_employee

        self.assertEqual(
            set(vars(get_ai_employee())),
            {"planning_engine", "workflow_coordinator"},
        )

    def test_approval_package_imports_no_capability_module(self):
        import app.services.ai_employee.approval as pkg

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
                    if tail in self._FORBIDDEN_CAPABILITY_MODULES:
                        offenders.append((filename, name))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
