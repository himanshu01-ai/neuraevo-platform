"""Planning Engine (Sprint 13.1 — reason, validate, explain; never execute).

The Planning Engine teaches the AI Employee to *think before acting*. It sits
between the Conversation Runtime and a future execution layer and coordinates
three injected, provider-independent collaborators:

    PlanningProvider.create_plan()          -> ExecutionPlan  (reasoning)
    PlanValidator.validate()                -> guarantees well-formedness
    PlanningExplanationBuilder.build()      -> human explanation

It performs NO action execution, tool calls, permission checks, persistence, or
AI/SDK work of its own — it only reasons (via the provider), guarantees the plan
is valid, and can explain it. The output of the engine is a validated
:class:`ExecutionPlan`; nothing downstream is triggered here.
"""

from typing import List, Optional

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.approval_models import ApprovalPlan
from app.services.planning.decision_engine import DecisionEngine
from app.services.planning.decision_models import ExecutionDecision
from app.services.planning.execution_coordinator import ExecutionCoordinator
from app.services.planning.execution_dependency_graph import (
    ExecutionDependencyGraphBuilder,
)
from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
)
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_intent_models import ExecutionIntent
from app.services.planning.human_approval_manager import HumanApprovalManager
from app.services.planning.execution_monitor import ExecutionMonitor
from app.services.planning.execution_monitor_models import (
    ExecutionMonitoringReport,
)
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
from app.services.planning.execution_queue_models import ExecutionQueue
from app.services.planning.execution_schedule_models import ExecutionSchedule
from app.services.planning.execution_scheduler import ExecutionScheduler
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.execution_state_models import ExecutionState
from app.services.planning.execution_workflow_models import ExecutionWorkflow
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine
from app.services.planning.task_lifecycle_models import TaskLifecycle
from app.services.planning.models import ExecutionPlan, PlanningRequest
from app.services.planning.recovery_manager import RecoveryManager
from app.services.planning.recovery_models import RecoveryPlan
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.plan_explanation_builder import (
    PlanningExplanationBuilder,
)
from app.services.planning.plan_validator import PlanValidator
from app.services.planning.providers.base import PlanningProvider


class PlanningEngine:
    """Coordinates provider planning, validation, and explanation.

    Collaborators are injected (Dependency Inversion): the planning provider that
    produces the plan, the validator that guarantees it is well-formed, and the
    explanation builder that renders it for a human. Stateless beyond those three
    references — it holds no session, repository, or cache — so provider or
    strategy replacement requires no change here. The engine never executes a
    step.
    """

    def __init__(
        self,
        provider: PlanningProvider,
        validator: PlanValidator,
        explanation_builder: PlanningExplanationBuilder,
        analyzer: Optional[PlanAnalyzer] = None,
        preparation_engine: Optional[ExecutionPreparationEngine] = None,
        decision_engine: Optional[DecisionEngine] = None,
        intent_engine: Optional[ExecutionIntentEngine] = None,
        orchestrator: Optional[ExecutionOrchestrator] = None,
        coordinator: Optional[ExecutionCoordinator] = None,
        lifecycle_engine: Optional[TaskLifecycleEngine] = None,
        state_manager: Optional[ExecutionStateManager] = None,
        dependency_graph_builder: Optional[
            ExecutionDependencyGraphBuilder
        ] = None,
        scheduler: Optional[ExecutionScheduler] = None,
        monitor: Optional[ExecutionMonitor] = None,
        recovery_manager: Optional[RecoveryManager] = None,
        approval_manager: Optional[HumanApprovalManager] = None,
    ) -> None:
        self.provider = provider
        self.validator = validator
        self.explanation_builder = explanation_builder
        # Sprint 13.2–13.14: the analyzer, preparation engine, decision engine,
        # execution-intent engine, execution orchestrator, execution
        # coordinator, task-lifecycle engine, execution-state manager,
        # dependency-graph builder, execution scheduler, execution monitor,
        # recovery manager, and human-approval manager are optional, additive
        # collaborators. Each is stored only when injected so that earlier-sprint
        # construction (three to fifteen arguments) keeps exactly its original
        # attributes and its tests pass unchanged. ``analyze``/``prepare``/
        # ``decide``/``create_execution_intent``/``create_execution_workflow``/
        # ``create_execution_queue``/``create_task_lifecycles``/
        # ``create_execution_state``/``create_execution_dependency_graph``/
        # ``create_execution_schedule``/``create_execution_monitoring_report``/
        # ``create_recovery_plan``/``create_approval_plan`` each require their
        # collaborator; ``create_plan``/``explain`` need none.
        if analyzer is not None:
            self.analyzer = analyzer
        if preparation_engine is not None:
            self.preparation_engine = preparation_engine
        if decision_engine is not None:
            self.decision_engine = decision_engine
        if intent_engine is not None:
            self.intent_engine = intent_engine
        if orchestrator is not None:
            self.orchestrator = orchestrator
        if coordinator is not None:
            self.coordinator = coordinator
        if lifecycle_engine is not None:
            self.lifecycle_engine = lifecycle_engine
        if state_manager is not None:
            self.state_manager = state_manager
        if dependency_graph_builder is not None:
            self.dependency_graph_builder = dependency_graph_builder
        if scheduler is not None:
            self.scheduler = scheduler
        if monitor is not None:
            self.monitor = monitor
        if recovery_manager is not None:
            self.recovery_manager = recovery_manager
        if approval_manager is not None:
            self.approval_manager = approval_manager

    def create_plan(self, request: PlanningRequest) -> ExecutionPlan:
        """Reason about ``request`` and return a validated :class:`ExecutionPlan`.

        Delegates plan construction to the provider, then validates the result
        so every plan the engine returns is guaranteed well-formed. A malformed
        plan raises :class:`PlanValidationError`; provider exceptions propagate
        unchanged. Nothing is executed.
        """
        plan = self.provider.create_plan(request)
        self.validator.validate(plan)
        return plan

    def explain(self, plan: ExecutionPlan) -> str:
        """Return a plain-language explanation of ``plan`` (explanation only)."""
        return self.explanation_builder.build(plan)

    def analyze(self, plan: ExecutionPlan) -> PlanAnalysis:
        """Analyse ``plan`` into a validated :class:`PlanAnalysis` (reasoning only).

        Sprint 13.2 addition. Delegates to the injected :class:`PlanAnalyzer`,
        then validates the result via the injected :class:`PlanValidator` so
        every analysis the engine returns is guaranteed well-formed. Determines
        whether the plan is ready, needs confirmation, needs clarification, or is
        missing information — but executes nothing. Raises :class:`RuntimeError`
        if no analyzer was injected, and :class:`PlanValidationError` if the
        analysis is malformed; analyzer exceptions propagate unchanged.
        """
        analyzer = getattr(self, "analyzer", None)
        if analyzer is None:
            raise RuntimeError(
                "PlanningEngine has no PlanAnalyzer injected; provide one to "
                "call analyze()."
            )
        analysis = analyzer.analyze(plan)
        self.validator.validate_analysis(analysis)
        return analysis

    def prepare(
        self, plan: ExecutionPlan, analysis: PlanAnalysis
    ) -> ExecutionPreparation:
        """Prepare ``plan`` for eventual execution (PREPARATION ONLY).

        Sprint 13.3 addition. Delegates to the injected
        :class:`ExecutionPreparationEngine` to determine which capabilities,
        services, and permissions the plan would require, how it would be
        sequenced, and what blocks it — then validates the result via the
        injected :class:`PlanValidator`. The ``analysis`` is accepted as the
        upstream reasoning context for this pipeline stage; the preparation is
        derived from the plan itself (which already carries the missing-info and
        confirmation signals). Nothing is executed, resolved, or acquired. Raises
        :class:`RuntimeError` if no preparation engine was injected and
        :class:`PlanValidationError` if the preparation is malformed; engine
        exceptions propagate unchanged.
        """
        preparation_engine = getattr(self, "preparation_engine", None)
        if preparation_engine is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionPreparationEngine injected; "
                "provide one to call prepare()."
            )
        preparation = preparation_engine.prepare(plan)
        self.validator.validate_preparation(preparation)
        return preparation

    def decide(
        self,
        plan: ExecutionPlan,
        analysis: PlanAnalysis,
        preparation: ExecutionPreparation,
    ) -> ExecutionDecision:
        """Decide whether ``plan`` may proceed (DECISION ONLY — no execution).

        Sprint 13.4 addition. Delegates to the injected :class:`DecisionEngine`
        to weigh the plan, its analysis, and its preparation into a single
        :class:`ExecutionDecision`, then validates the result via the injected
        :class:`PlanValidator`. This only classifies readiness — it executes,
        resolves, and acquires nothing. Raises :class:`RuntimeError` if no
        decision engine was injected and :class:`PlanValidationError` if the
        decision is malformed; engine exceptions propagate unchanged.
        """
        decision_engine = getattr(self, "decision_engine", None)
        if decision_engine is None:
            raise RuntimeError(
                "PlanningEngine has no DecisionEngine injected; provide one to "
                "call decide()."
            )
        decision = decision_engine.decide(plan, analysis, preparation)
        self.validator.validate_decision(decision)
        return decision

    def create_execution_intent(
        self,
        plan: ExecutionPlan,
        analysis: PlanAnalysis,
        preparation: ExecutionPreparation,
        decision: ExecutionDecision,
    ) -> ExecutionIntent:
        """Convert ``decision`` into an :class:`ExecutionIntent` (no execution).

        Sprint 13.5 addition. Delegates to the injected
        :class:`ExecutionIntentEngine` to turn the decision (with its plan,
        analysis, and preparation as context) into a single provider-independent
        intent, then validates the result via the injected
        :class:`PlanValidator`. This only records an intention — it executes,
        resolves, and acquires nothing. Raises :class:`RuntimeError` if no intent
        engine was injected and :class:`PlanValidationError` if the intent is
        malformed; engine exceptions propagate unchanged.
        """
        intent_engine = getattr(self, "intent_engine", None)
        if intent_engine is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionIntentEngine injected; provide "
                "one to call create_execution_intent()."
            )
        intent = intent_engine.create_intent(
            plan, analysis, preparation, decision
        )
        self.validator.validate_execution_intent(intent)
        return intent

    def create_execution_workflow(
        self,
        plan: ExecutionPlan,
        analysis: PlanAnalysis,
        preparation: ExecutionPreparation,
        decision: ExecutionDecision,
        intent: ExecutionIntent,
    ) -> ExecutionWorkflow:
        """Coordinate ``plan`` into an :class:`ExecutionWorkflow` (no execution).

        Sprint 13.6 addition. Delegates to the injected
        :class:`ExecutionOrchestrator` to turn the intent (with its plan,
        analysis, preparation, and decision as context) into a provider-
        independent, ordered, grouped workflow, then validates the result via the
        injected :class:`PlanValidator`. This coordinates planning only — it
        executes, resolves, and acquires nothing. Raises :class:`RuntimeError` if
        no orchestrator was injected and :class:`PlanValidationError` if the
        workflow is malformed; orchestrator exceptions propagate unchanged.
        """
        orchestrator = getattr(self, "orchestrator", None)
        if orchestrator is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionOrchestrator injected; provide "
                "one to call create_execution_workflow()."
            )
        workflow = orchestrator.create_workflow(
            plan, analysis, preparation, decision, intent
        )
        self.validator.validate_execution_workflow(workflow)
        return workflow

    def create_execution_queue(
        self, workflow: ExecutionWorkflow
    ) -> ExecutionQueue:
        """Organise ``workflow`` into an :class:`ExecutionQueue` (no execution).

        Sprint 13.7 addition. Delegates to the injected
        :class:`ExecutionCoordinator` to convert the workflow's steps into
        ordered execution units with deterministic statuses and counts, then
        validates the result via the injected :class:`PlanValidator`. This
        organises execution only — it executes, resolves, and acquires nothing.
        Raises :class:`RuntimeError` if no coordinator was injected and
        :class:`PlanValidationError` if the queue is malformed; coordinator
        exceptions propagate unchanged.
        """
        coordinator = getattr(self, "coordinator", None)
        if coordinator is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionCoordinator injected; provide "
                "one to call create_execution_queue()."
            )
        queue = coordinator.create_queue(workflow)
        self.validator.validate_execution_queue(queue)
        return queue

    def create_task_lifecycles(
        self, queue: ExecutionQueue
    ) -> List[TaskLifecycle]:
        """Manage lifecycles for ``queue``'s units (STATE ONLY — no execution).

        Sprint 13.8 addition. Delegates to the injected
        :class:`TaskLifecycleEngine` to build one immutable :class:`TaskLifecycle`
        per execution unit — starting state, allowed transitions, terminal flag,
        and immutable history — then validates the result via the injected
        :class:`PlanValidator`. This represents execution state only; it executes,
        resolves, and acquires nothing and never mutates the queue. Raises
        :class:`RuntimeError` if no lifecycle engine was injected and
        :class:`PlanValidationError` if a lifecycle is malformed; engine
        exceptions propagate unchanged.
        """
        lifecycle_engine = getattr(self, "lifecycle_engine", None)
        if lifecycle_engine is None:
            raise RuntimeError(
                "PlanningEngine has no TaskLifecycleEngine injected; provide "
                "one to call create_task_lifecycles()."
            )
        lifecycles = lifecycle_engine.create_lifecycles(queue)
        self.validator.validate_task_lifecycles(lifecycles)
        return lifecycles

    def create_execution_state(
        self, lifecycles: List[TaskLifecycle]
    ) -> ExecutionState:
        """Aggregate ``lifecycles`` into an :class:`ExecutionState` (STATE ONLY).

        Sprint 13.9 addition. Delegates to the injected
        :class:`ExecutionStateManager` to aggregate the task lifecycles into a
        single overall state — counts, progress, active ids, and terminal flag —
        then validates the result via the injected :class:`PlanValidator`. This
        represents execution state only; it executes, resolves, and acquires
        nothing and never mutates the lifecycles. Raises :class:`RuntimeError` if
        no state manager was injected and :class:`PlanValidationError` if the
        state is malformed; manager exceptions propagate unchanged.
        """
        state_manager = getattr(self, "state_manager", None)
        if state_manager is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionStateManager injected; provide "
                "one to call create_execution_state()."
            )
        state = state_manager.create_state(lifecycles)
        self.validator.validate_execution_state(state)
        return state

    def create_execution_dependency_graph(
        self, queue: ExecutionQueue, lifecycles: List[TaskLifecycle]
    ) -> ExecutionDependencyGraph:
        """Model task relationships as an :class:`ExecutionDependencyGraph`.

        Sprint 13.10 addition. Delegates to the injected
        :class:`ExecutionDependencyGraphBuilder` to build a deterministic
        dependency graph from the queue and its lifecycles — nodes, edges, roots,
        leaves, ready/blocked sets, and cycle detection — then validates the
        result via the injected :class:`PlanValidator`. This models relationships
        only; it executes, resolves, and acquires nothing and never mutates the
        queue or lifecycles. Raises :class:`RuntimeError` if no builder was
        injected and :class:`PlanValidationError` if the graph is malformed;
        builder exceptions propagate unchanged.
        """
        dependency_graph_builder = getattr(
            self, "dependency_graph_builder", None
        )
        if dependency_graph_builder is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionDependencyGraphBuilder "
                "injected; provide one to call "
                "create_execution_dependency_graph()."
            )
        graph = dependency_graph_builder.build_graph(queue, lifecycles)
        self.validator.validate_execution_dependency_graph(graph)
        return graph

    def create_execution_schedule(
        self, graph: ExecutionDependencyGraph, state: ExecutionState
    ) -> ExecutionSchedule:
        """Determine what could run next as an :class:`ExecutionSchedule`.

        Sprint 13.11 addition. Delegates to the injected
        :class:`ExecutionScheduler` to select schedulable nodes, defer the rest,
        keep blocked nodes blocked, and compute a deterministic execution order
        from the dependency graph and execution state, then validates the result
        via the injected :class:`PlanValidator`. This determines what could run
        only; it executes, resolves, and acquires nothing and never mutates its
        inputs. Raises :class:`RuntimeError` if no scheduler was injected and
        :class:`PlanValidationError` if the schedule is malformed; scheduler
        exceptions propagate unchanged.
        """
        scheduler = getattr(self, "scheduler", None)
        if scheduler is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionScheduler injected; provide one "
                "to call create_execution_schedule()."
            )
        schedule = scheduler.create_schedule(graph, state)
        self.validator.validate_execution_schedule(schedule)
        return schedule

    def create_execution_monitoring_report(
        self, schedule: ExecutionSchedule, state: ExecutionState
    ) -> ExecutionMonitoringReport:
        """Observe execution as an :class:`ExecutionMonitoringReport` (no execution).

        Sprint 13.12 addition. Delegates to the injected :class:`ExecutionMonitor`
        to group the schedule's nodes into active, pending, blocked, and completed
        sets, echo the execution state's status and progress, and derive an
        overall health, then validates the result via the injected
        :class:`PlanValidator`. This observes execution only; it executes,
        resolves, and acquires nothing and never mutates its inputs. Raises
        :class:`RuntimeError` if no monitor was injected and
        :class:`PlanValidationError` if the report is malformed; monitor
        exceptions propagate unchanged.
        """
        monitor = getattr(self, "monitor", None)
        if monitor is None:
            raise RuntimeError(
                "PlanningEngine has no ExecutionMonitor injected; provide one "
                "to call create_execution_monitoring_report()."
            )
        report = monitor.create_report(schedule, state)
        self.validator.validate_execution_monitoring_report(report)
        return report

    def create_recovery_plan(
        self,
        report: ExecutionMonitoringReport,
        state: ExecutionState,
        graph: ExecutionDependencyGraph,
    ) -> RecoveryPlan:
        """Plan recovery from ``report`` as a :class:`RecoveryPlan` (no execution).

        Sprint 13.13 addition. Delegates to the injected :class:`RecoveryManager`
        to read the observed health, identify the affected nodes, partition them
        into recoverable and unrecoverable, select a recovery strategy, and decide
        whether a human must step in, then validates the result via the injected
        :class:`PlanValidator`. This plans recovery only; it retries, resumes, and
        executes nothing and never mutates its inputs. Raises :class:`RuntimeError`
        if no recovery manager was injected and :class:`PlanValidationError` if the
        plan is malformed; manager exceptions propagate unchanged.
        """
        recovery_manager = getattr(self, "recovery_manager", None)
        if recovery_manager is None:
            raise RuntimeError(
                "PlanningEngine has no RecoveryManager injected; provide one to "
                "call create_recovery_plan()."
            )
        recovery_plan = recovery_manager.create_recovery_plan(
            report, state, graph
        )
        self.validator.validate_recovery_plan(recovery_plan)
        return recovery_plan

    def create_approval_plan(
        self,
        intent: ExecutionIntent,
        schedule: ExecutionSchedule,
        recovery: RecoveryPlan,
    ) -> ApprovalPlan:
        """Govern approval of an execution as an :class:`ApprovalPlan` (no execution).

        Sprint 13.14 addition. Delegates to the injected
        :class:`HumanApprovalManager` to decide whether human sign-off is
        required, build deterministic checkpoints over the scheduled units,
        identify the pending approvals, and mark cleared versus held nodes, then
        validates the result via the injected :class:`PlanValidator`. This governs
        approval only; it requests approval, resumes, retries, and executes
        nothing and never mutates its inputs. Raises :class:`RuntimeError` if no
        approval manager was injected and :class:`PlanValidationError` if the plan
        is malformed; manager exceptions propagate unchanged.
        """
        approval_manager = getattr(self, "approval_manager", None)
        if approval_manager is None:
            raise RuntimeError(
                "PlanningEngine has no HumanApprovalManager injected; provide "
                "one to call create_approval_plan()."
            )
        approval_plan = approval_manager.create_approval_plan(
            intent, schedule, recovery
        )
        self.validator.validate_approval_plan(approval_plan)
        return approval_plan
