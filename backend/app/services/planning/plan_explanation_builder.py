"""Plan explanation builder (Sprint 13.1 — human narration, no execution).

Turns an :class:`ExecutionPlan` into a single, plain-language sentence a person
can read to understand what the AI Employee intends to do — for example:

    "To plan your trip, I will first understand the destination, then review
    your calendar, ... and finally await your approval. I won't take any action
    until you approve the plan."

Explanation only: it reads the plan's data and produces text. It performs no
execution, provider, AI, or runtime work.
"""

from typing import List

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.decision_models import DecisionStatus, ExecutionDecision
from app.services.planning.execution_intent_models import (
    ExecutionIntent,
    ExecutionIntentType,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
from app.services.planning.execution_queue_models import (
    ExecutionQueue,
    QueueStatus,
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
    TaskLifecycle,
    TaskLifecycleState,
)

# User-language message per decision status (no implementation terms).
_DECISION_MESSAGES = {
    DecisionStatus.APPROVED.value: "Everything's in place, so I can go ahead.",
    DecisionStatus.WAITING_FOR_INFORMATION.value: (
        "I'm waiting on some details before I can proceed."
    ),
    DecisionStatus.WAITING_FOR_CONFIRMATION.value: (
        "I'm ready, but I'll wait for your confirmation before proceeding."
    ),
    DecisionStatus.BLOCKED.value: (
        "I can't proceed yet — some requirements still need to be met."
    ),
    DecisionStatus.REJECTED.value: (
        "I can't carry out this plan as it stands."
    ),
}

# User-language message per execution intent (no implementation terms).
_INTENT_MESSAGES = {
    ExecutionIntentType.EXECUTE_NOW.value: (
        "I'm ready to carry this out now."
    ),
    ExecutionIntentType.WAIT_FOR_USER.value: (
        "I need something from you before I can continue."
    ),
    ExecutionIntentType.DEFER.value: (
        "I'll set this aside until the requirements are met."
    ),
    ExecutionIntentType.CANCEL.value: (
        "I won't pursue this plan."
    ),
}

# User-language message per workflow status (no implementation terms).
_WORKFLOW_STATUS_MESSAGES = {
    WorkflowStatus.READY.value: "The workflow is ready to run.",
    WorkflowStatus.WAITING.value: (
        "The workflow is waiting and will continue once you respond."
    ),
    WorkflowStatus.BLOCKED.value: (
        "The workflow is on hold until its requirements are met."
    ),
    WorkflowStatus.PLANNED.value: (
        "The workflow is planned but won't proceed."
    ),
}

# User-language phrasing per execution mode.
_WORKFLOW_MODE_PHRASES = {
    ExecutionMode.SEQUENTIAL.value: "one step at a time",
    ExecutionMode.PARALLEL.value: "several steps at once",
    ExecutionMode.HYBRID.value: "a mix of sequential and parallel steps",
}

# User-language message per overall execution state (no implementation terms).
_EXECUTION_STATE_MESSAGES = {
    ExecutionStateType.READY.value: "Execution is ready to begin.",
    ExecutionStateType.WAITING.value: "Execution is waiting.",
    ExecutionStateType.RUNNING.value: "Execution is in progress.",
    ExecutionStateType.PARTIALLY_COMPLETED.value: (
        "Execution is partly done."
    ),
    ExecutionStateType.COMPLETED.value: "Execution is complete.",
    ExecutionStateType.FAILED.value: "Execution ran into a problem.",
    ExecutionStateType.CANCELLED.value: "Execution was cancelled.",
}

# User-language message per queue status (no implementation terms).
_QUEUE_STATUS_MESSAGES = {
    QueueStatus.READY.value: "The execution queue is ready to begin.",
    QueueStatus.WAITING.value: (
        "The execution queue is waiting for you before anything can start."
    ),
    QueueStatus.BLOCKED.value: (
        "The execution queue is blocked; nothing can start yet."
    ),
}


class PlanningExplanationBuilder:
    """Stateless renderer of a plan into a human-readable explanation.

    Holds no state and owns no session or provider. ``build`` narrates the
    ordered steps with ``first``/``then``/``finally`` connectors and appends the
    plan's confirmation intent and any open questions.
    """

    def build(self, plan: ExecutionPlan) -> str:
        """Return a plain-language explanation of ``plan`` (no execution).

        Narrates the steps in order, then notes that no action is taken until
        approval (when the plan requires confirmation) and what details are still
        needed (when ``missing_information`` is non-empty).
        """
        if not plan.steps:
            return f"I have no steps planned yet to {self._lower_first(plan.goal)}."

        phrases = [self._lower_first(step.description) for step in plan.steps]
        body = self._narrate(phrases)
        sentence = f"To {self._lower_first(plan.goal)}, {body}."

        if plan.requires_user_confirmation:
            sentence += " I won't take any action until you approve the plan."

        if plan.missing_information:
            needs = self._join(plan.missing_information)
            sentence += f" First, I'll need a few details from you: {needs}."

        return sentence

    def build_with_analysis(
        self, plan: ExecutionPlan, analysis: PlanAnalysis
    ) -> str:
        """Explain ``plan`` and fold in the ``analysis`` conclusions (no execution).

        Sprint 13.2 extension that reuses :meth:`build` for the step narration,
        then, per the analysis: prepends a clarification note when clarification
        is required, appends a confirmation note when confirmation is required,
        and appends a readiness note when the plan is ready. Explanation only —
        nothing is executed.
        """
        segments: List[str] = []
        if analysis.requires_clarification:
            segments.append(
                "I need a little more information before I can continue."
            )
        segments.append(self.build(plan))
        if analysis.requires_confirmation:
            segments.append(
                "I'll wait for your confirmation before executing."
            )
        if analysis.ready_for_execution:
            segments.append("The plan is ready for execution.")
        return " ".join(segments)

    def build_with_preparation(
        self, plan: ExecutionPlan, preparation: ExecutionPreparation
    ) -> str:
        """Explain ``plan`` and what it would take to carry it out (no execution).

        Sprint 13.3 extension. Reuses :meth:`build` for the step narration, then
        describes — in everyday user language, never implementation terms — which
        capabilities and services would be used, which permissions would be
        needed, and whether it can start now or what still stands in the way.
        """
        segments: List[str] = [self.build(plan)]

        if preparation.required_capabilities:
            segments.append(
                "To do this I'll use "
                f"{self._join(preparation.required_capabilities)}."
            )
        if preparation.external_services:
            segments.append(
                "It connects to "
                f"{self._join(preparation.external_services)}."
            )
        if preparation.permissions_required:
            segments.append(
                "I'll need your permission for "
                f"{self._join(preparation.permissions_required)}."
            )
        if preparation.can_execute_immediately:
            segments.append("I can start on this right away.")
        else:
            outstanding = self._join(
                [self._readable_blocker(item) for item in preparation.blocked_by]
            )
            segments.append(
                f"Before I can start, these still need to be resolved: "
                f"{outstanding}."
            )
        return " ".join(segments)

    def build_with_decision(
        self, plan: ExecutionPlan, decision: ExecutionDecision
    ) -> str:
        """Explain ``plan`` and the decision reached about it (no execution).

        Sprint 13.4 extension. Reuses :meth:`build` for the step narration, then
        adds a plain-language statement of the decision and, when the plan cannot
        proceed, the outstanding items — in everyday user language, never
        implementation terms.
        """
        segments: List[str] = [self.build(plan)]
        segments.append(
            _DECISION_MESSAGES.get(decision.status, decision.reason)
        )
        if (
            decision.blocking_reasons
            and decision.status != DecisionStatus.APPROVED.value
        ):
            readable = [
                self._readable_blocker(item)
                for item in decision.blocking_reasons
            ]
            segments.append(f"Outstanding items: {self._join(readable)}.")
        return " ".join(segments)

    def build_with_execution_intent(
        self, plan: ExecutionPlan, intent: ExecutionIntent
    ) -> str:
        """Explain ``plan`` and the intent formed about it (no execution).

        Sprint 13.5 extension. Reuses :meth:`build` for the step narration, then
        adds a plain-language statement of the intent and, when deferring, the
        reason — in everyday user language, never implementation terms.
        """
        segments: List[str] = [self.build(plan)]
        segments.append(
            _INTENT_MESSAGES.get(intent.intent, intent.recommended_next_step)
        )
        if (
            intent.intent == ExecutionIntentType.DEFER.value
            and intent.defer_reason.strip()
        ):
            segments.append(intent.defer_reason)
        return " ".join(segments)

    def build_with_execution_workflow(
        self, plan: ExecutionPlan, workflow: ExecutionWorkflow
    ) -> str:
        """Explain ``plan`` and the workflow coordinating it (no execution).

        Sprint 13.6 extension. Reuses :meth:`build` for the step narration, then
        describes the workflow's status, how its steps are organised, and whether
        it can be resumed — in everyday user language, never implementation
        terms.
        """
        segments: List[str] = [self.build(plan)]
        segments.append(
            _WORKFLOW_STATUS_MESSAGES.get(
                workflow.workflow_status, "The workflow is planned."
            )
        )
        phrase = _WORKFLOW_MODE_PHRASES.get(
            workflow.execution_mode, "in order"
        )
        segments.append(
            f"It's organised to run {phrase} across "
            f"{workflow.estimated_total_steps} steps."
        )
        if workflow.resumable:
            segments.append("It can be paused and resumed.")
        return " ".join(segments)

    def build_with_execution_state(
        self, plan: ExecutionPlan, state: ExecutionState
    ) -> str:
        """Explain ``plan`` and the overall execution state (no execution).

        Sprint 13.9 extension. Reuses :meth:`build` for the step narration, then
        states the overall progress in everyday user language, never
        implementation terms.
        """
        segments: List[str] = [self.build(plan)]
        segments.append(
            _EXECUTION_STATE_MESSAGES.get(
                state.overall_state, "Execution is planned."
            )
        )
        segments.append(
            f"Progress: {state.progress_percentage:.0f}% "
            f"({state.completed_tasks} of {state.total_tasks} tasks complete)."
        )
        return " ".join(segments)

    def build_with_task_lifecycles(
        self, plan: ExecutionPlan, lifecycles: List[TaskLifecycle]
    ) -> str:
        """Explain ``plan`` and the lifecycles tracking its tasks (no execution).

        Sprint 13.8 extension. Reuses :meth:`build` for the step narration, then
        summarises how many tasks are being tracked and how many are ready or
        waiting — in everyday user language, never implementation terms.
        """
        segments: List[str] = [self.build(plan)]
        if not lifecycles:
            segments.append("There are no tasks to track yet.")
            return " ".join(segments)

        ready = sum(
            1
            for lifecycle in lifecycles
            if lifecycle.current_state == TaskLifecycleState.READY.value
        )
        waiting = sum(
            1
            for lifecycle in lifecycles
            if lifecycle.current_state == TaskLifecycleState.WAITING.value
        )
        segments.append(
            f"I'm tracking {len(lifecycles)} tasks: {ready} ready to start and "
            f"{waiting} waiting."
        )
        return " ".join(segments)

    def build_with_execution_queue(
        self, plan: ExecutionPlan, queue: ExecutionQueue
    ) -> str:
        """Explain ``plan`` and the queue organising its steps (no execution).

        Sprint 13.7 extension. Reuses :meth:`build` for the step narration, then
        describes the queue's status and how many items are ready or blocked — in
        everyday user language, never implementation terms.
        """
        segments: List[str] = [self.build(plan)]
        segments.append(
            _QUEUE_STATUS_MESSAGES.get(
                queue.status, "The execution queue is planned."
            )
        )
        segments.append(
            f"It has {queue.total_units} items — {queue.ready_units} ready and "
            f"{queue.blocked_units} blocked."
        )
        return " ".join(segments)

    @staticmethod
    def _readable_blocker(blocker: str) -> str:
        """Render a ``Need X`` blocker as user-friendly ``X`` (else unchanged)."""
        prefix = "Need "
        return blocker[len(prefix):] if blocker.startswith(prefix) else blocker

    @staticmethod
    def _narrate(phrases: List[str]) -> str:
        """Join step phrases with ``first``/``then``/``finally`` connectors."""
        if len(phrases) == 1:
            return f"I will {phrases[0]}"

        connectors = ["first"] + ["then"] * (len(phrases) - 2) + ["finally"]
        parts = [
            f"{connector} {phrase}"
            for connector, phrase in zip(connectors, phrases)
        ]
        return "I will " + ", ".join(parts[:-1]) + f", and {parts[-1]}"

    @staticmethod
    def _join(items: List[str]) -> str:
        """Join labels into a natural ``a``, ``b``, and ``c`` list."""
        cleaned = [item.strip() for item in items if item.strip()]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"

    @staticmethod
    def _lower_first(text: str) -> str:
        """Lower-case only the first character for mid-sentence readability."""
        stripped = text.strip()
        if not stripped:
            return stripped
        return stripped[0].lower() + stripped[1:]
