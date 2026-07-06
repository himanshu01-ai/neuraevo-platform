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
