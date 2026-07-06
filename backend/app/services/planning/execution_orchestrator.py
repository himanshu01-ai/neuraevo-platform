"""Execution orchestrator (Sprint 13.6 — deterministic workflow construction).

Reasoning-only component that transforms an :class:`ExecutionIntent` (weighed
alongside its :class:`ExecutionPlan`, :class:`PlanAnalysis`,
:class:`ExecutionPreparation`, and :class:`ExecutionDecision`) into an immutable,
provider-independent :class:`ExecutionWorkflow`. It coordinates execution
*planning* only: it orders and groups steps, assigns a status and mode, and marks
resumability — but it never executes, resolves, or acquires anything.

Fully deterministic and offline: no AI, network, SDK, Runtime, Registry,
Permission, Tool execution, Memory, or Gemini. Same inputs in -> same workflow
out.
"""

import hashlib
from typing import List

from app.services.planning.analysis_models import PlanAnalysis
from app.services.planning.decision_models import ExecutionDecision
from app.services.planning.execution_intent_models import (
    ExecutionIntent,
    ExecutionIntentType,
)
from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
)
from app.services.planning.execution_workflow_models import (
    ExecutionMode,
    ExecutionWorkflow,
    WorkflowStatus,
    WorkflowStep,
)
from app.services.planning.models import ExecutionPlan

# Preparation strategy label -> workflow execution mode.
_STRATEGY_TO_MODE = {
    "Sequential": ExecutionMode.SEQUENTIAL.value,
    "Parallel": ExecutionMode.PARALLEL.value,
    "Hybrid": ExecutionMode.HYBRID.value,
}

# Intent -> workflow status.
_INTENT_TO_STATUS = {
    ExecutionIntentType.EXECUTE_NOW.value: WorkflowStatus.READY.value,
    ExecutionIntentType.WAIT_FOR_USER.value: WorkflowStatus.WAITING.value,
    ExecutionIntentType.DEFER.value: WorkflowStatus.BLOCKED.value,
    ExecutionIntentType.CANCEL.value: WorkflowStatus.PLANNED.value,
}


class ExecutionOrchestrator:
    """Stateless builder: (plan, …, intent) -> :class:`ExecutionWorkflow`.

    Holds no state and owns no session, provider, or cache. It preserves the
    plan's step order, groups steps by the chosen execution mode, assigns a
    status from the intent, and marks the workflow resumable unless it is merely
    planned (cancelled). It never executes a step.
    """

    def create_workflow(
        self,
        plan: ExecutionPlan,
        analysis: PlanAnalysis,
        preparation: ExecutionPreparation,
        decision: ExecutionDecision,
        intent: ExecutionIntent,
    ) -> ExecutionWorkflow:
        """Return a deterministic :class:`ExecutionWorkflow` (no execution).

        The execution mode comes from the preparation strategy; the status from
        the intent; the steps preserve the plan's order and dependencies and are
        grouped by mode. The analysis is accepted as upstream context. Nothing is
        executed.
        """
        mode = _STRATEGY_TO_MODE.get(
            preparation.execution_strategy, ExecutionMode.SEQUENTIAL.value
        )
        ordered_steps = self._ordered_steps(plan, mode)
        status = _INTENT_TO_STATUS[intent.intent]
        resumable = status != WorkflowStatus.PLANNED.value
        group_count = len({step.group for step in ordered_steps})

        return ExecutionWorkflow(
            workflow_id=self._workflow_id(plan),
            workflow_status=status,
            ordered_steps=ordered_steps,
            estimated_total_steps=len(ordered_steps),
            execution_mode=mode,
            resumable=resumable,
            metadata={
                "source_intent": intent.intent,
                "decision_status": decision.status,
                "execution_mode": mode,
                "group_count": group_count,
            },
        )

    @classmethod
    def _ordered_steps(cls, plan: ExecutionPlan, mode: str) -> List[WorkflowStep]:
        """Preserve plan order and dependencies, grouping steps by ``mode``."""
        steps: List[WorkflowStep] = []
        for position, step in enumerate(plan.steps, start=1):
            steps.append(
                WorkflowStep(
                    step_number=step.step_number,
                    description=step.description,
                    group=cls._group_index(mode, position),
                    depends_on=list(step.dependencies),
                )
            )
        return steps

    @staticmethod
    def _group_index(mode: str, position: int) -> int:
        """Assign a 1-based execution group for a step at ``position`` by mode.

        ``PARALLEL`` places every step in one group; ``HYBRID`` groups steps in
        consecutive pairs; ``SEQUENTIAL`` gives each step its own group.
        """
        if mode == ExecutionMode.PARALLEL.value:
            return 1
        if mode == ExecutionMode.HYBRID.value:
            return ((position - 1) // 2) + 1
        return position

    @staticmethod
    def _workflow_id(plan: ExecutionPlan) -> str:
        """Derive a stable, deterministic id from the plan's goal and steps."""
        raw = "|".join(
            [plan.goal, *[step.description for step in plan.steps]]
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"wf-{digest}"
