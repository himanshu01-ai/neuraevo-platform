"""Plan validator (Sprint 13.1 — structural/logical guarantees).

Provider-independent validation that every :class:`ExecutionPlan` the engine
returns is well-formed before it reaches a caller (or, later, an execution
layer). It inspects only the plan's plain data and performs NO execution,
provider, AI, or runtime work.

Rules enforced:

* **Non-empty** — a plan must contain at least one step.
* **No duplicate steps** — ``step_number`` values are unique, and step
  descriptions are distinct.
* **Logical ordering** — step numbers are exactly ``1..N`` in order.
* **Dependency correctness** — every dependency references a distinct, earlier
  step that exists; no step depends on itself or on a later step.
"""

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.decision_models import DecisionStatus, ExecutionDecision
from app.services.planning.execution_intent_models import (
    ExecutionIntent,
    ExecutionIntentType,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
    ExecutionStrategy,
)
from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    ExecutionUnitStatus,
    QueueStatus,
)
from app.services.planning.execution_dependency_graph_models import (
    ExecutionDependencyGraph,
)
from app.services.planning.execution_schedule_models import (
    ExecutionSchedule,
    SchedulingStrategy,
)
from app.services.planning.execution_state_models import (
    ExecutionState,
    ExecutionStateType,
)
from app.services.planning.execution_workflow_models import (
    ExecutionMode,
    ExecutionWorkflow,
    WorkflowStatus,
)
from app.services.planning.models import ExecutionPlan
from app.services.planning.task_lifecycle_models import (
    TASK_LIFECYCLE_TRANSITIONS,
    TERMINAL_TASK_STATES,
    TaskLifecycle,
    TaskLifecycleState,
)

# The only execution strategies a well-formed preparation may carry.
_VALID_STRATEGIES = frozenset(strategy.value for strategy in ExecutionStrategy)

# The only statuses a well-formed decision may carry.
_VALID_DECISION_STATUSES = frozenset(status.value for status in DecisionStatus)

# The only intents a well-formed execution intent may carry.
_VALID_INTENT_TYPES = frozenset(
    intent.value for intent in ExecutionIntentType
)

# The only statuses/modes a well-formed execution workflow may carry.
_VALID_WORKFLOW_STATUSES = frozenset(
    status.value for status in WorkflowStatus
)
_VALID_EXECUTION_MODES = frozenset(mode.value for mode in ExecutionMode)

# The only statuses a well-formed queue / execution unit may carry.
_VALID_QUEUE_STATUSES = frozenset(status.value for status in QueueStatus)
_VALID_UNIT_STATUSES = frozenset(
    status.value for status in ExecutionUnitStatus
)

# The only states a well-formed task lifecycle may carry.
_VALID_LIFECYCLE_STATES = frozenset(
    state.value for state in TaskLifecycleState
)

# The only strategies a well-formed execution schedule may carry.
_VALID_SCHEDULING_STRATEGIES = frozenset(
    strategy.value for strategy in SchedulingStrategy
)

# The only overall states a well-formed execution state may carry.
_VALID_EXECUTION_STATES = frozenset(
    state.value for state in ExecutionStateType
)
# The overall states that represent a fully terminated execution.
_TERMINAL_EXECUTION_STATES = frozenset(
    {
        ExecutionStateType.COMPLETED.value,
        ExecutionStateType.FAILED.value,
        ExecutionStateType.CANCELLED.value,
    }
)


class PlanValidationError(ValueError):
    """Raised when an :class:`ExecutionPlan` violates a structural/logical rule.

    Subclasses :class:`ValueError` so callers may treat it as an ordinary
    validation failure. The message names the specific rule that failed.
    """


class PlanValidator:
    """Stateless validator for :class:`ExecutionPlan` well-formedness.

    Holds no state and owns no session, provider, or cache. ``validate`` raises
    :class:`PlanValidationError` on the first rule violation and otherwise
    returns ``None``; ``is_valid`` is a boolean convenience over it.
    """

    def validate(self, plan: ExecutionPlan) -> None:
        """Raise :class:`PlanValidationError` if ``plan`` is not well-formed.

        Checks emptiness, duplicate steps, logical ordering, then per-step
        dependency correctness — in that order — so the raised message points at
        the most fundamental problem first.
        """
        steps = plan.steps

        # 1. Empty plans are not plannable output.
        if not steps:
            raise PlanValidationError(
                "Plan has no steps; an empty plan is not valid."
            )

        step_numbers = [step.step_number for step in steps]

        # 2a. Duplicate step numbers.
        if len(set(step_numbers)) != len(step_numbers):
            raise PlanValidationError(
                f"Duplicate step numbers found: {step_numbers}."
            )

        # 2b. Duplicate step descriptions (case-insensitive, trimmed).
        normalized = [step.description.strip().lower() for step in steps]
        if len(set(normalized)) != len(normalized):
            raise PlanValidationError(
                "Duplicate step descriptions found; steps must be distinct."
            )

        # 3. Logical ordering: numbers must be exactly 1..N in listed order.
        expected = list(range(1, len(steps) + 1))
        if step_numbers != expected:
            raise PlanValidationError(
                "Step numbers must be sequential 1.."
                f"{len(steps)} in order; got {step_numbers}."
            )

        # 4. Dependency correctness (all dependencies precede their step).
        valid_numbers = set(step_numbers)
        for step in steps:
            dependencies = step.dependencies

            if len(set(dependencies)) != len(dependencies):
                raise PlanValidationError(
                    f"Step {step.step_number} has duplicate dependencies: "
                    f"{dependencies}."
                )

            for dependency in dependencies:
                if dependency == step.step_number:
                    raise PlanValidationError(
                        f"Step {step.step_number} depends on itself."
                    )
                if dependency not in valid_numbers:
                    raise PlanValidationError(
                        f"Step {step.step_number} depends on unknown step "
                        f"{dependency}."
                    )
                if dependency > step.step_number:
                    raise PlanValidationError(
                        f"Step {step.step_number} depends on later step "
                        f"{dependency}; dependencies must come earlier."
                    )

    def is_valid(self, plan: ExecutionPlan) -> bool:
        """Return ``True`` if ``plan`` passes :meth:`validate`, else ``False``."""
        try:
            self.validate(plan)
        except PlanValidationError:
            return False
        return True

    def validate_analysis(self, analysis: PlanAnalysis) -> None:
        """Raise :class:`PlanValidationError` if ``analysis`` is not well-formed.

        Sprint 13.2 extension. Rejects a confidence outside ``0.0``–``1.0``
        (defence-in-depth; the DTO also enforces this and would reject it at
        construction), and empty or duplicate entries in either
        ``missing_information`` or ``clarification_questions``. Inspects only the
        analysis's plain data — no execution, provider, or AI work.
        """
        if not 0.0 <= analysis.confidence <= 1.0:
            raise PlanValidationError(
                f"Confidence {analysis.confidence} is outside 0.0..1.0."
            )
        self._reject_empty_or_duplicate(
            analysis.missing_information, "missing information"
        )
        self._reject_empty_or_duplicate(
            analysis.clarification_questions, "clarification question"
        )

    def validate_preparation(self, preparation: ExecutionPreparation) -> None:
        """Raise :class:`PlanValidationError` if ``preparation`` is not well-formed.

        Sprint 13.3 extension. Rejects a negative step count, an execution
        strategy outside the allowed set, and empty or duplicate entries in the
        capability, permission, external-service, or blocker lists. Inspects only
        the preparation's plain data — no execution, provider, or AI work.
        """
        if preparation.estimated_execution_steps < 0:
            raise PlanValidationError(
                "estimated_execution_steps cannot be negative "
                f"({preparation.estimated_execution_steps})."
            )
        if preparation.execution_strategy not in _VALID_STRATEGIES:
            raise PlanValidationError(
                f"Invalid execution strategy: "
                f"{preparation.execution_strategy!r}."
            )
        self._reject_empty_or_duplicate(
            preparation.required_capabilities, "capability"
        )
        self._reject_empty_or_duplicate(
            preparation.permissions_required, "permission"
        )
        self._reject_empty_or_duplicate(
            preparation.external_services, "external service"
        )
        self._reject_empty_or_duplicate(preparation.blocked_by, "blocker")

    def validate_decision(self, decision: ExecutionDecision) -> None:
        """Raise :class:`PlanValidationError` if ``decision`` is not well-formed.

        Sprint 13.4 extension. Rejects an unknown status, an empty reason, a
        confidence outside ``0.0``–``1.0``, an inconsistent ``can_execute`` (true
        only when ``APPROVED``), an ``APPROVED`` decision that still lists
        blockers, and empty or duplicate blocking reasons. Inspects only the
        decision's plain data — no execution, provider, or AI work.
        """
        if decision.status not in _VALID_DECISION_STATUSES:
            raise PlanValidationError(
                f"Invalid decision status: {decision.status!r}."
            )
        if not decision.reason.strip():
            raise PlanValidationError("Decision reason must not be empty.")
        if not 0.0 <= decision.confidence <= 1.0:
            raise PlanValidationError(
                f"Confidence {decision.confidence} is outside 0.0..1.0."
            )
        if decision.can_execute and (
            decision.status != DecisionStatus.APPROVED.value
        ):
            raise PlanValidationError(
                "can_execute may be true only when the decision is APPROVED."
            )
        if decision.status == DecisionStatus.APPROVED.value and (
            decision.blocking_reasons
        ):
            raise PlanValidationError(
                "An APPROVED decision must have no blocking reasons."
            )
        self._reject_empty_or_duplicate(
            decision.blocking_reasons, "blocking reason"
        )

    def validate_execution_intent(self, intent: ExecutionIntent) -> None:
        """Raise :class:`PlanValidationError` if ``intent`` is not well-formed.

        Sprint 13.5 extension. Rejects an unknown intent, an empty recommended
        next step, a negative execution priority, an inconsistent
        ``should_execute`` (true only for ``EXECUTE_NOW``) or
        ``requires_user_action`` (true only for ``WAIT_FOR_USER``), and a
        ``DEFER`` intent with no defer reason. Inspects only the intent's plain
        data — no execution, provider, or AI work.
        """
        if intent.intent not in _VALID_INTENT_TYPES:
            raise PlanValidationError(
                f"Invalid execution intent: {intent.intent!r}."
            )
        if not intent.recommended_next_step.strip():
            raise PlanValidationError(
                "Recommended next step must not be empty."
            )
        if intent.execution_priority < 0:
            raise PlanValidationError(
                "execution_priority cannot be negative "
                f"({intent.execution_priority})."
            )
        if intent.should_execute and (
            intent.intent != ExecutionIntentType.EXECUTE_NOW.value
        ):
            raise PlanValidationError(
                "should_execute may be true only when the intent is "
                "EXECUTE_NOW."
            )
        if intent.requires_user_action and (
            intent.intent != ExecutionIntentType.WAIT_FOR_USER.value
        ):
            raise PlanValidationError(
                "requires_user_action may be true only when the intent is "
                "WAIT_FOR_USER."
            )
        if intent.intent == ExecutionIntentType.DEFER.value and (
            not intent.defer_reason.strip()
        ):
            raise PlanValidationError(
                "A DEFER intent must include a defer reason."
            )

    def validate_execution_workflow(self, workflow: ExecutionWorkflow) -> None:
        """Raise :class:`PlanValidationError` if ``workflow`` is not well-formed.

        Sprint 13.6 extension. Rejects an empty workflow id, an unknown status or
        execution mode, a negative or inconsistent step count, duplicate step
        numbers, and a non-positive group index. Inspects only the workflow's
        plain data — no execution, provider, or AI work.
        """
        if not workflow.workflow_id.strip():
            raise PlanValidationError("workflow_id must not be empty.")
        if workflow.workflow_status not in _VALID_WORKFLOW_STATUSES:
            raise PlanValidationError(
                f"Invalid workflow status: {workflow.workflow_status!r}."
            )
        if workflow.execution_mode not in _VALID_EXECUTION_MODES:
            raise PlanValidationError(
                f"Invalid execution mode: {workflow.execution_mode!r}."
            )
        if workflow.estimated_total_steps < 0:
            raise PlanValidationError(
                "estimated_total_steps cannot be negative "
                f"({workflow.estimated_total_steps})."
            )
        if workflow.estimated_total_steps != len(workflow.ordered_steps):
            raise PlanValidationError(
                "estimated_total_steps must equal the number of ordered steps."
            )
        step_numbers = [step.step_number for step in workflow.ordered_steps]
        if len(set(step_numbers)) != len(step_numbers):
            raise PlanValidationError(
                f"Duplicate workflow step numbers: {step_numbers}."
            )
        for step in workflow.ordered_steps:
            if step.group < 1:
                raise PlanValidationError(
                    f"Workflow step {step.step_number} has a non-positive "
                    f"group ({step.group})."
                )

    def validate_execution_queue(self, queue: ExecutionQueue) -> None:
        """Raise :class:`PlanValidationError` if ``queue`` is not well-formed.

        Sprint 13.7 extension. Rejects an empty queue or workflow id, an unknown
        queue status, an unknown unit status, an empty unit id, a non-positive
        unit group, negative counts, a total that disagrees with the number of
        units, duplicate unit ids or step numbers, and ready/blocked counts that
        do not match the units. Inspects only the queue's plain data — no
        execution, provider, or AI work.
        """
        if not queue.queue_id.strip():
            raise PlanValidationError("queue_id must not be empty.")
        if not queue.workflow_id.strip():
            raise PlanValidationError("workflow_id must not be empty.")
        if queue.status not in _VALID_QUEUE_STATUSES:
            raise PlanValidationError(
                f"Invalid queue status: {queue.status!r}."
            )
        if (
            queue.total_units < 0
            or queue.ready_units < 0
            or queue.blocked_units < 0
        ):
            raise PlanValidationError("Queue counts cannot be negative.")
        if queue.total_units != len(queue.execution_units):
            raise PlanValidationError(
                "total_units must equal the number of execution units."
            )

        unit_ids: list = []
        step_numbers: list = []
        ready = 0
        blocked = 0
        for unit in queue.execution_units:
            if unit.status not in _VALID_UNIT_STATUSES:
                raise PlanValidationError(
                    f"Invalid execution unit status: {unit.status!r}."
                )
            if not unit.unit_id.strip():
                raise PlanValidationError("unit_id must not be empty.")
            if unit.execution_group < 1:
                raise PlanValidationError(
                    f"Execution unit {unit.step_number} has a non-positive "
                    f"group ({unit.execution_group})."
                )
            unit_ids.append(unit.unit_id)
            step_numbers.append(unit.step_number)
            if unit.status == ExecutionUnitStatus.READY.value:
                ready += 1
            elif unit.status == ExecutionUnitStatus.BLOCKED.value:
                blocked += 1

        if len(set(unit_ids)) != len(unit_ids):
            raise PlanValidationError("Duplicate execution unit ids.")
        if len(set(step_numbers)) != len(step_numbers):
            raise PlanValidationError(
                f"Duplicate execution unit step numbers: {step_numbers}."
            )
        if queue.ready_units != ready:
            raise PlanValidationError(
                "ready_units does not match the number of READY units."
            )
        if queue.blocked_units != blocked:
            raise PlanValidationError(
                "blocked_units does not match the number of BLOCKED units."
            )

    def validate_task_lifecycles(
        self, lifecycles: "list[TaskLifecycle]"
    ) -> None:
        """Raise :class:`PlanValidationError` if any lifecycle is not well-formed.

        Sprint 13.8 extension. For each lifecycle, rejects an empty unit id, an
        unknown current/previous state, allowed next states that disagree with
        the canonical transition table, an ``is_terminal`` flag inconsistent with
        that table, an empty history, a history not ending at the current state, a
        history that violates the transition table, a ``previous_state``
        inconsistent with the history, and (across the list) duplicate unit ids.
        Inspects only plain data — no execution, provider, or AI work.
        """
        unit_ids: list = []
        for lifecycle in lifecycles:
            if not lifecycle.unit_id.strip():
                raise PlanValidationError("unit_id must not be empty.")
            if lifecycle.current_state not in _VALID_LIFECYCLE_STATES:
                raise PlanValidationError(
                    f"Invalid lifecycle state: {lifecycle.current_state!r}."
                )
            if lifecycle.previous_state is not None and (
                lifecycle.previous_state not in _VALID_LIFECYCLE_STATES
            ):
                raise PlanValidationError(
                    f"Invalid previous state: {lifecycle.previous_state!r}."
                )

            expected_next = set(
                TASK_LIFECYCLE_TRANSITIONS[lifecycle.current_state]
            )
            if set(lifecycle.allowed_next_states) != expected_next:
                raise PlanValidationError(
                    f"allowed_next_states for {lifecycle.current_state} must be "
                    f"{sorted(expected_next)}."
                )
            expected_terminal = (
                lifecycle.current_state in TERMINAL_TASK_STATES
            )
            if lifecycle.is_terminal != expected_terminal:
                raise PlanValidationError(
                    f"is_terminal for {lifecycle.current_state} must be "
                    f"{expected_terminal}."
                )

            history = lifecycle.state_history
            if not history:
                raise PlanValidationError("state_history must not be empty.")
            for state in history:
                if state not in _VALID_LIFECYCLE_STATES:
                    raise PlanValidationError(
                        f"Invalid state in history: {state!r}."
                    )
            if history[-1] != lifecycle.current_state:
                raise PlanValidationError(
                    "state_history must end at the current state."
                )
            for earlier, later in zip(history, history[1:]):
                if later not in TASK_LIFECYCLE_TRANSITIONS[earlier]:
                    raise PlanValidationError(
                        f"Invalid history transition {earlier} -> {later}."
                    )
            expected_previous = history[-2] if len(history) >= 2 else None
            if lifecycle.previous_state != expected_previous:
                raise PlanValidationError(
                    "previous_state must match the state before current in "
                    "history."
                )
            unit_ids.append(lifecycle.unit_id)

        if len(set(unit_ids)) != len(unit_ids):
            raise PlanValidationError("Duplicate task lifecycle unit ids.")

    def validate_execution_state(self, state: ExecutionState) -> None:
        """Raise :class:`PlanValidationError` if ``state`` is not well-formed.

        Sprint 13.9 extension. Rejects an empty execution id, an unknown overall
        state, negative counts, per-state counts that exceed the total, a
        progress percentage outside ``0``–``100``, a ``terminal`` flag
        inconsistent with the terminal counts, an overall state that disagrees
        with a terminal execution, and empty, duplicate, or miscounted active
        task ids. Inspects only the state's plain data — no execution, provider,
        or AI work.
        """
        if not state.execution_id.strip():
            raise PlanValidationError("execution_id must not be empty.")
        if state.overall_state not in _VALID_EXECUTION_STATES:
            raise PlanValidationError(
                f"Invalid overall state: {state.overall_state!r}."
            )

        counts = (
            state.ready_tasks,
            state.waiting_tasks,
            state.running_tasks,
            state.completed_tasks,
            state.failed_tasks,
            state.cancelled_tasks,
            state.skipped_tasks,
        )
        if state.total_tasks < 0 or any(count < 0 for count in counts):
            raise PlanValidationError("Execution counts cannot be negative.")
        if sum(counts) > state.total_tasks:
            raise PlanValidationError(
                "Per-state task counts cannot exceed total_tasks."
            )
        if not 0.0 <= state.progress_percentage <= 100.0:
            raise PlanValidationError(
                f"progress_percentage {state.progress_percentage} is outside "
                "0..100."
            )

        terminal_count = (
            state.completed_tasks
            + state.failed_tasks
            + state.cancelled_tasks
            + state.skipped_tasks
        )
        expected_terminal = (
            state.total_tasks > 0 and terminal_count == state.total_tasks
        )
        if state.terminal != expected_terminal:
            raise PlanValidationError(
                "terminal must be true exactly when every task is terminal."
            )
        if state.terminal and (
            state.overall_state not in _TERMINAL_EXECUTION_STATES
        ):
            raise PlanValidationError(
                "A terminal execution state must be COMPLETED, FAILED, or "
                "CANCELLED."
            )

        if any(not task_id.strip() for task_id in state.active_task_ids):
            raise PlanValidationError("active_task_ids must not be empty.")
        if len(set(state.active_task_ids)) != len(state.active_task_ids):
            raise PlanValidationError("Duplicate active task ids.")
        if len(state.active_task_ids) != state.total_tasks - terminal_count:
            raise PlanValidationError(
                "active_task_ids count must equal the non-terminal task count."
            )

    def validate_execution_dependency_graph(
        self, graph: ExecutionDependencyGraph
    ) -> None:
        """Raise :class:`PlanValidationError` if ``graph`` is not well-formed.

        Sprint 13.10 extension. Rejects an empty graph id, duplicate node ids,
        empty node/unit ids, a node marked both/neither ready and blocked,
        dependency/dependent/edge references to unknown nodes, self-edges, and
        root/leaf/ready/blocked sets that disagree with the nodes. Inspects only
        the graph's plain data — no execution, provider, or AI work.
        """
        if not graph.graph_id.strip():
            raise PlanValidationError("graph_id must not be empty.")

        node_ids = [node.node_id for node in graph.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise PlanValidationError("Duplicate graph node ids.")
        known = set(node_ids)

        for node in graph.nodes:
            if not node.node_id.strip():
                raise PlanValidationError("node_id must not be empty.")
            if not node.execution_unit_id.strip():
                raise PlanValidationError("execution_unit_id must not be empty.")
            if node.ready == node.blocked:
                raise PlanValidationError(
                    f"Node {node.node_id} must be exactly one of ready/blocked."
                )
            for dependency in node.dependencies:
                if dependency not in known:
                    raise PlanValidationError(
                        f"Node {node.node_id} depends on unknown node "
                        f"{dependency}."
                    )
            for dependent in node.dependents:
                if dependent not in known:
                    raise PlanValidationError(
                        f"Node {node.node_id} has unknown dependent "
                        f"{dependent}."
                    )

        for edge in graph.edges:
            if edge.source_node not in known or edge.target_node not in known:
                raise PlanValidationError(
                    "An edge references an unknown node."
                )
            if edge.source_node == edge.target_node:
                raise PlanValidationError(
                    f"Self-edge on node {edge.source_node} is not allowed."
                )

        self._reject_node_set(
            graph.root_nodes,
            {n.node_id for n in graph.nodes if not n.dependencies},
            "root",
        )
        self._reject_node_set(
            graph.leaf_nodes,
            {n.node_id for n in graph.nodes if not n.dependents},
            "leaf",
        )
        self._reject_node_set(
            graph.ready_nodes,
            {n.node_id for n in graph.nodes if n.ready},
            "ready",
        )
        self._reject_node_set(
            graph.blocked_nodes,
            {n.node_id for n in graph.nodes if n.blocked},
            "blocked",
        )

    def validate_execution_schedule(self, schedule: ExecutionSchedule) -> None:
        """Raise :class:`PlanValidationError` if ``schedule`` is not well-formed.

        Sprint 13.11 extension. Rejects an empty schedule/execution id, an unknown
        scheduling strategy, a scheduled node with an empty id, empty unit id,
        negative priority, ``scheduled`` not true, or empty reason; duplicate
        scheduled node ids; an execution order that does not match the scheduled
        nodes; empty or duplicate deferred/blocked ids; and scheduled/deferred/
        blocked sets that overlap. Inspects only the schedule's plain data — no
        execution, provider, or AI work.
        """
        if not schedule.schedule_id.strip():
            raise PlanValidationError("schedule_id must not be empty.")
        if not schedule.execution_id.strip():
            raise PlanValidationError("execution_id must not be empty.")
        if schedule.scheduling_strategy not in _VALID_SCHEDULING_STRATEGIES:
            raise PlanValidationError(
                f"Invalid scheduling strategy: "
                f"{schedule.scheduling_strategy!r}."
            )

        scheduled_ids: list = []
        for node in schedule.scheduled_nodes:
            if not node.node_id.strip():
                raise PlanValidationError("scheduled node_id must not be empty.")
            if not node.execution_unit_id.strip():
                raise PlanValidationError("execution_unit_id must not be empty.")
            if node.priority < 0:
                raise PlanValidationError(
                    f"Scheduled node {node.node_id} has negative priority."
                )
            if not node.scheduled:
                raise PlanValidationError(
                    "scheduled_nodes must have scheduled=True."
                )
            if not node.reason.strip():
                raise PlanValidationError("scheduled node reason is empty.")
            scheduled_ids.append(node.node_id)

        if len(set(scheduled_ids)) != len(scheduled_ids):
            raise PlanValidationError("Duplicate scheduled node ids.")

        if len(schedule.execution_order) != len(scheduled_ids):
            raise PlanValidationError(
                "execution_order must list exactly the scheduled nodes."
            )
        if len(set(schedule.execution_order)) != len(schedule.execution_order):
            raise PlanValidationError("Duplicate ids in execution_order.")
        if set(schedule.execution_order) != set(scheduled_ids):
            raise PlanValidationError(
                "execution_order must match the scheduled nodes."
            )

        self._reject_empty_or_duplicate(schedule.deferred_nodes, "deferred node")
        self._reject_empty_or_duplicate(schedule.blocked_nodes, "blocked node")

        scheduled_set = set(scheduled_ids)
        deferred_set = set(schedule.deferred_nodes)
        blocked_set = set(schedule.blocked_nodes)
        if (
            scheduled_set & deferred_set
            or scheduled_set & blocked_set
            or deferred_set & blocked_set
        ):
            raise PlanValidationError(
                "scheduled, deferred, and blocked nodes must be disjoint."
            )

    @staticmethod
    def _reject_node_set(actual: list, expected: set, label: str) -> None:
        """Reject duplicate entries or a mismatch against ``expected`` node ids."""
        if len(set(actual)) != len(actual):
            raise PlanValidationError(f"Duplicate {label} node ids.")
        if set(actual) != expected:
            raise PlanValidationError(
                f"{label}_nodes do not match the graph's {label} nodes."
            )

    @staticmethod
    def _reject_empty_or_duplicate(items: list, label: str) -> None:
        """Reject empty/whitespace entries and case-insensitive duplicates."""
        cleaned = [item.strip() for item in items]
        if any(not item for item in cleaned):
            raise PlanValidationError(f"Empty {label} entry is not allowed.")
        lowered = [item.lower() for item in cleaned]
        if len(set(lowered)) != len(lowered):
            raise PlanValidationError(
                f"Duplicate {label} entries are not allowed."
            )
