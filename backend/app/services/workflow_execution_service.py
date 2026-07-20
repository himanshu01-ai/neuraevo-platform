"""Workflow execution service (Sprint 18.6 — the authoring↔runtime adapter).

Bridges the two domains the sprint keeps separate: it takes an *authored*
workflow (Sprint 18.3), checks it may run, translates its graph into runtime
steps (``workflow_translation``), and hands them to the existing Sprint 15.15
:class:`WorkflowCoordinator`. It owns the execution *business rules* — ownership,
the published-only gate, translation — and nothing else; the coordinator owns
execution semantics and is not touched.

Ownership and lifecycle are not re-implemented here: it reuses
:class:`WorkflowService`, so there is one definition of "who owns this" and
"what state is it in". The runtime's result models never cross this boundary as
themselves — the router maps them into the API's own DTOs.
"""

import uuid
from dataclasses import dataclass
from typing import List, Optional

from app.models.user import User
from app.models.workflow_execution import WorkflowExecution
from app.services.runtime.capability_contracts import validate_inputs
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import WorkflowExecutionResult, WorkflowStep
from app.services.workflow_execution_history_service import (
    TRIGGER_MANUAL,
    WorkflowExecutionHistoryService,
    utc_now,
)
from app.services.workflow_execution_recorder import (
    ExecutionLog,
    TimingCapabilityRouter,
)
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowService,
    WorkflowValidationError,
)
from app.services.workflow_translation import WorkflowTranslationError, translate_graph
from app.utils.constants import WorkflowStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

_COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class TrackedExecution:
    """A run and the record of it (Sprint 18.10).

    Two facts that used to be one: what the runtime produced, and the row that
    remembers it. The endpoint needs both — the result to answer with, and the
    execution's id so the caller can come back to it later.
    """

    result: WorkflowExecutionResult
    execution: WorkflowExecution


class WorkflowExecutionService:
    """Runs a published workflow through the runtime coordinator.

    Constructed with the request-scoped session and the injected
    :class:`WorkflowCoordinator` (constructor injection; it instantiates
    neither). Reuses :class:`WorkflowService` for ownership and lifecycle, and
    since Sprint 18.10 :class:`WorkflowExecutionHistoryService` for remembering
    what happened.
    """

    def __init__(
        self,
        session,
        coordinator: WorkflowCoordinator,
        history: Optional[WorkflowExecutionHistoryService] = None,
    ) -> None:
        self.session = session
        self.coordinator = coordinator
        self.workflows = WorkflowService(session)
        self.history = history

    def execute_workflow(
        self,
        owner: User,
        workflow_id: uuid.UUID,
        initial_inputs: dict | None = None,
        recorder: Optional[TimingCapabilityRouter] = None,
    ) -> WorkflowExecutionResult:
        """Run one workflow and return the runtime's result.

        Raises before running when the workflow can't be executed:

        * :class:`WorkflowNotFoundError` / :class:`WorkflowAccessDeniedError` —
          from the reused ownership check (missing, or another user's).
        * :class:`InvalidStatusTransitionError` — it is a draft or archived, so
          not runnable.
        * :class:`WorkflowValidationError` — its graph can't be translated into
          runnable steps, or a step is missing an input its capability needs
          (checked against the canonical contract, Sprint 18.8).

        A workflow that runs but whose step fails does *not* raise: the
        coordinator reports a ``FAILED`` result, which is returned as-is. The
        caller distinguishes "couldn't start" (an exception) from "ran and
        failed" (a result) — they are different facts.

        Passing a ``recorder`` times each step. It is the router the coordinator
        dispatches through, so the timings are taken without the engine knowing
        it is being watched (Sprint 18.10). Omitting it runs exactly as before.
        """
        # Ownership + existence, reused. Raises not-found / access-denied.
        workflow = self.workflows.get_workflow(owner, workflow_id)

        self._require_runnable(workflow)

        try:
            steps = translate_graph(workflow.graph)
        except WorkflowTranslationError as exc:
            # Surface translation problems in the workflow domain's vocabulary,
            # the same way the service wraps graph-validation errors.
            raise WorkflowValidationError(str(exc)) from exc

        self._require_configured(steps)

        logger.info(
            "User %s executing workflow %s (%d steps)",
            owner.id,
            workflow.id,
            len(steps),
        )
        # A recorder is installed by rebuilding the coordinator over the same
        # collaborators, not by reaching into the one we were given: the engine
        # takes its router by injection, so watching it needs no change to it.
        coordinator = self.coordinator
        if recorder is not None:
            coordinator = WorkflowCoordinator(
                recorder, self.coordinator.artifact_coordinator
            )

        result = coordinator.execute(
            steps,
            workflow_id=str(workflow.id),
            initial_inputs=initial_inputs or None,
        )
        logger.info(
            "Workflow %s finished: %s (%d/%d steps)",
            workflow.id,
            result.workflow_status,
            result.completed_step_count,
            result.total_step_count,
        )
        return result

    def execute_and_record(
        self,
        owner: User,
        workflow_id: uuid.UUID,
        *,
        initial_inputs: dict | None = None,
        trigger: str = TRIGGER_MANUAL,
        retry_of_execution_id: Optional[uuid.UUID] = None,
    ) -> TrackedExecution:
        """Run a workflow and remember what it did (Sprint 18.10).

        The same run as :meth:`execute_workflow`, observed: the clock is read
        either side of it, each step is timed through the recorder, and the
        outcome is written to history before the caller sees it.

        A refusal — not published, untranslatable, not yours — raises as it
        always did and writes nothing. Nothing ran, so there is no run to
        remember, and a history full of things that never started would make the
        list useless for the question it exists to answer.
        """
        if self.history is None:  # pragma: no cover - wiring guarantees one
            raise RuntimeError("This service was built without execution history.")

        recorder = TimingCapabilityRouter(self.coordinator.router)
        started_at = utc_now()
        result = self.execute_workflow(
            owner, workflow_id, initial_inputs=initial_inputs, recorder=recorder
        )
        finished_at = utc_now()

        execution = self.history.record(
            owner=owner,
            workflow_id=workflow_id,
            result=result,
            started_at=started_at,
            finished_at=finished_at,
            recorder=recorder,
            log=self._build_log(result, recorder),
            trigger=trigger,
            retry_of_execution_id=retry_of_execution_id,
        )
        return TrackedExecution(result=result, execution=execution)

    @staticmethod
    def _build_log(
        result: WorkflowExecutionResult, recorder: TimingCapabilityRouter
    ) -> ExecutionLog:
        """The structured account of a run, assembled from what it produced.

        Written after the fact rather than as it happens: everything worth
        saying is in the result, and building it here keeps the run itself free
        of logging concerns.

        Every message is one already meant for a person. The runtime's own
        failure reason is passed through; no exception type, traceback or
        internal identifier is added to it.
        """
        log = ExecutionLog()
        log.info(f"Started {result.total_step_count} step(s).")

        for reference in result.step_references:
            timing = recorder.timing_for(reference.step_id)
            took = f" in {timing.duration_ms}ms" if timing else ""
            if reference.execution_status == _COMPLETED:
                log.info(
                    f"{reference.capability_name} step completed{took}.",
                    reference.step_id,
                )
            else:
                log.error(
                    f"{reference.capability_name} step did not complete{took}.",
                    reference.step_id,
                )

        if result.workflow_status == _COMPLETED:
            log.info(
                f"Finished — {result.completed_step_count} of "
                f"{result.total_step_count} step(s) completed."
            )
        else:
            reason = str(result.result_metadata.get("error") or "").strip()
            # The coordinator's "step failed: <id>" restates the step already
            # named on the record, so it is not repeated as a message.
            if reason and not reason.lower().startswith("step failed:"):
                log.error(reason, result.failed_step_id)
            log.error(
                f"Stopped — {result.completed_step_count} of "
                f"{result.total_step_count} step(s) completed.",
                result.failed_step_id,
            )

        return log

    @staticmethod
    def _require_configured(steps: List[WorkflowStep]) -> None:
        """Refuse a workflow whose steps are missing inputs they need.

        Checked against the canonical contract (Sprint 18.8), so a step that
        could only fail on its first instruction is turned away before anything
        runs — an incomplete workflow gets one clear answer naming every step at
        fault, rather than a run that dies at the first of them.

        Only what the contract records is checked. Whether a path exists or an
        address is deliverable is the capability's to discover, and a run is the
        honest way to find out.
        """
        problems: List[str] = []
        for step in steps:
            messages = validate_inputs(step.capability_name, step.inputs)
            if not messages:
                continue
            name = str(step.step_metadata.get("name") or "").strip() or step.step_id
            problems.extend(f"{name}: {message}" for message in messages)

        if problems:
            raise WorkflowValidationError(
                "This workflow isn't ready to run. " + " ".join(problems)
            )

    @staticmethod
    def _require_runnable(workflow) -> None:
        """Only a published workflow runs. Draft and archived are refused."""
        status = workflow.status
        if status == WorkflowStatus.ARCHIVED.value:
            raise InvalidStatusTransitionError(
                "An archived workflow can't be run. Restore it first."
            )
        if status != WorkflowStatus.PUBLISHED.value:
            raise InvalidStatusTransitionError(
                "Only a published workflow can be run. Publish it first."
            )
