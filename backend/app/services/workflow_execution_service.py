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

from app.models.user import User
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.runtime.workflow_models import WorkflowExecutionResult
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowService,
    WorkflowValidationError,
)
from app.services.workflow_translation import WorkflowTranslationError, translate_graph
from app.utils.constants import WorkflowStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowExecutionService:
    """Runs a published workflow through the runtime coordinator.

    Constructed with the request-scoped session and the injected
    :class:`WorkflowCoordinator` (constructor injection; it instantiates
    neither). Reuses :class:`WorkflowService` for ownership and lifecycle.
    """

    def __init__(self, session, coordinator: WorkflowCoordinator) -> None:
        self.session = session
        self.coordinator = coordinator
        self.workflows = WorkflowService(session)

    def execute_workflow(
        self,
        owner: User,
        workflow_id: uuid.UUID,
        initial_inputs: dict | None = None,
    ) -> WorkflowExecutionResult:
        """Run one workflow and return the runtime's result.

        Raises before running when the workflow can't be executed:

        * :class:`WorkflowNotFoundError` / :class:`WorkflowAccessDeniedError` —
          from the reused ownership check (missing, or another user's).
        * :class:`InvalidStatusTransitionError` — it is a draft or archived, so
          not runnable.
        * :class:`WorkflowValidationError` — its graph can't be translated into
          runnable steps.

        A workflow that runs but whose step fails does *not* raise: the
        coordinator reports a ``FAILED`` result, which is returned as-is. The
        caller distinguishes "couldn't start" (an exception) from "ran and
        failed" (a result) — they are different facts.
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

        logger.info(
            "User %s executing workflow %s (%d steps)",
            owner.id,
            workflow.id,
            len(steps),
        )
        result = self.coordinator.execute(
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
