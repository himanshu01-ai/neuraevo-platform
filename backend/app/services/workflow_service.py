"""Workflow service: the authored-workflow domain's business logic.

Sits between the API layer and the repository layer and owns every decision:
ownership, lifecycle transitions, graph validity, and name uniqueness.
Repositories persist; this decides.

Mirrors :mod:`app.services.employee_service` deliberately — same error
vocabulary, same ownership check, same unit-of-work responsibility — so the two
domains behave identically at their edges.

Nothing here executes a workflow. Sprint 15.15's runtime coordinator runs steps
it is handed and does not read this domain; this layer only persists structure.
"""

import copy
import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from app.models.user import User
from app.models.workflow import Workflow
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services.workflow_graph import (
    WorkflowGraphError,
    empty_graph,
    validate_graph,
)
from app.services.workflow_lifecycle import RESTORABLE_STATUSES, can_transition
from app.utils.constants import WorkflowStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

# How a duplicate names itself when the caller supplies nothing.
_COPY_SUFFIX = " (copy)"


class WorkflowError(Exception):
    """Base class for workflow-related domain errors."""


class WorkflowNotFoundError(WorkflowError):
    """Raised when no workflow exists for the given identifier."""


class WorkflowAccessDeniedError(WorkflowError):
    """Raised when a workflow exists but is owned by another user."""


class WorkflowValidationError(WorkflowError):
    """Raised when a request would leave the workflow in an invalid state."""


class InvalidStatusTransitionError(WorkflowError):
    """Raised when a status change is not permitted from the current status."""


class WorkflowService:
    """Coordinates workflow operations using the repository layer.

    The service owns the unit of work: the repository ``flush``es while the
    service is responsible for committing the transaction.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.workflows = WorkflowRepository(session)

    # --- Creation --------------------------------------------------------

    def create_workflow(self, owner: User, data: WorkflowCreate) -> Workflow:
        """Create a new workflow owned by ``owner`` and persist it."""
        name = self._clean_name(data.name)
        self._require_unique_name(owner.id, name)
        graph = self._validated_graph(data.graph)

        workflow = self.workflows.create(
            owner.id,
            name=name,
            description=data.description,
            graph=graph,
            status=WorkflowStatus.DRAFT.value,
        )
        self.session.commit()
        self.session.refresh(workflow)
        logger.info("User %s created workflow %s", owner.id, workflow.id)
        return workflow

    # --- Reads -----------------------------------------------------------

    def list_workflows(self, owner: User) -> Sequence[Workflow]:
        """Return all of ``owner``'s workflows."""
        return self.workflows.list_by_user(owner.id)

    def get_workflow(self, owner: User, workflow_id: uuid.UUID) -> Workflow:
        """Return a single workflow the ``owner`` is allowed to access.

        Raises :class:`WorkflowNotFoundError` if it does not exist, or
        :class:`WorkflowAccessDeniedError` if it belongs to another user.
        """
        workflow = self.workflows.get_by_id(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(str(workflow_id))
        if workflow.user_id != owner.id:
            logger.warning(
                "User %s attempted to access workflow %s owned by %s",
                owner.id,
                workflow_id,
                workflow.user_id,
            )
            raise WorkflowAccessDeniedError(str(workflow_id))
        return workflow

    # --- Update ----------------------------------------------------------

    def update_workflow(
        self, owner: User, workflow_id: uuid.UUID, data: WorkflowUpdate
    ) -> Workflow:
        """Apply a partial update. Only supplied fields change.

        An archived workflow is read-only: editing one silently would let a
        retired workflow drift from what was archived, so it must be restored
        first.
        """
        workflow = self.get_workflow(owner, workflow_id)

        if workflow.status == WorkflowStatus.ARCHIVED.value:
            raise InvalidStatusTransitionError(
                "An archived workflow cannot be edited. Restore it first."
            )

        fields: dict[str, object] = {}

        if data.name is not None:
            name = self._clean_name(data.name)
            self._require_unique_name(owner.id, name, exclude_id=workflow.id)
            fields["name"] = name

        if data.description is not None:
            fields["description"] = data.description

        if data.graph is not None:
            fields["graph"] = self._validated_graph(data.graph)

        if data.status is not None:
            current = self._status_of(workflow)
            if not can_transition(current, data.status):
                raise InvalidStatusTransitionError(
                    f"A workflow cannot move from {current.value} to "
                    f"{data.status.value}."
                )
            # Archiving through an update would bypass the archive endpoint's
            # bookkeeping, so it is refused here and directed to that endpoint.
            if data.status is WorkflowStatus.ARCHIVED:
                raise InvalidStatusTransitionError(
                    "Use the archive endpoint to archive a workflow."
                )
            fields["status"] = data.status.value

        if fields:
            self.workflows.update_fields(workflow, **fields)
            self.session.commit()
            self.session.refresh(workflow)
        return workflow

    # --- Lifecycle -------------------------------------------------------

    def archive_workflow(self, owner: User, workflow_id: uuid.UUID) -> Workflow:
        """Retire a workflow without destroying it."""
        workflow = self.get_workflow(owner, workflow_id)

        if workflow.status == WorkflowStatus.ARCHIVED.value:
            raise InvalidStatusTransitionError(
                "That workflow is already archived."
            )

        self.workflows.set_status(
            workflow,
            WorkflowStatus.ARCHIVED.value,
            archived_at=datetime.now(timezone.utc),
        )
        self.session.commit()
        self.session.refresh(workflow)
        logger.info("User %s archived workflow %s", owner.id, workflow.id)
        return workflow

    def restore_workflow(
        self,
        owner: User,
        workflow_id: uuid.UUID,
        target: WorkflowStatus = WorkflowStatus.DRAFT,
    ) -> Workflow:
        """Bring an archived workflow back.

        A restore returns it to the bench (``draft``), never straight back into
        publication — republishing is a decision its owner makes afterwards.
        """
        workflow = self.get_workflow(owner, workflow_id)

        if self._status_of(workflow) is not WorkflowStatus.ARCHIVED:
            raise InvalidStatusTransitionError(
                "Only an archived workflow can be restored."
            )

        if target not in RESTORABLE_STATUSES:
            raise InvalidStatusTransitionError(
                f"A workflow cannot be restored directly to {target.value}."
            )

        self.workflows.set_status(workflow, target.value, archived_at=None)
        self.session.commit()
        self.session.refresh(workflow)
        logger.info("User %s restored workflow %s", owner.id, workflow.id)
        return workflow

    # --- Duplicate -------------------------------------------------------

    def duplicate_workflow(
        self,
        owner: User,
        workflow_id: uuid.UUID,
        name: Optional[str] = None,
    ) -> Workflow:
        """Copy a workflow's structure into a new draft.

        The clone starts as a draft regardless of the source's status: a copy
        has not been reviewed, and inheriting ``published`` would release
        something nobody approved. Archived workflows can be duplicated —
        copying a retired structure is how you resume from it.
        """
        source = self.get_workflow(owner, workflow_id)
        clone_name = self._clean_name(name) if name else self._copy_name(owner, source)
        self._require_unique_name(owner.id, clone_name)

        clone = self.workflows.create(
            owner.id,
            name=clone_name,
            description=source.description,
            # Deep-copied through validation so the clone never shares the
            # source's mutable document.
            graph=validate_graph(copy.deepcopy(source.graph)),
            status=WorkflowStatus.DRAFT.value,
        )
        self.session.commit()
        self.session.refresh(clone)
        logger.info(
            "User %s duplicated workflow %s into %s", owner.id, source.id, clone.id
        )
        return clone

    # --- Delete ----------------------------------------------------------

    def delete_workflow(self, owner: User, workflow_id: uuid.UUID) -> None:
        """Delete a workflow permanently."""
        workflow = self.get_workflow(owner, workflow_id)
        self.workflows.delete(workflow)
        self.session.commit()
        logger.info("User %s deleted workflow %s", owner.id, workflow_id)

    # --- Internals -------------------------------------------------------

    @staticmethod
    def _status_of(workflow: Workflow) -> WorkflowStatus:
        try:
            return WorkflowStatus(workflow.status)
        except ValueError:
            # A row holding a value outside the vocabulary is treated as a
            # draft rather than crashing the request.
            return WorkflowStatus.DRAFT

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise WorkflowValidationError("A workflow needs a name.")
        return cleaned

    @staticmethod
    def _validated_graph(graph: Optional[dict]) -> dict:
        if graph is None:
            return empty_graph()
        try:
            return validate_graph(graph)
        except WorkflowGraphError as exc:
            raise WorkflowValidationError(str(exc)) from exc

    def _require_unique_name(
        self,
        user_id: uuid.UUID,
        name: str,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """One name per owner. Two identical rows in a list are unusable."""
        if self.workflows.count_by_name(user_id, name, exclude_id=exclude_id):
            raise WorkflowValidationError(
                f"You already have a workflow named {name!r}."
            )

    def _copy_name(self, owner: User, source: Workflow) -> str:
        """``Name (copy)``, then ``Name (copy 2)``… until one is free."""
        base = f"{source.name}{_COPY_SUFFIX}"
        if not self.workflows.count_by_name(owner.id, base):
            return base
        suffix = 2
        while self.workflows.count_by_name(owner.id, f"{base} {suffix}"):
            suffix += 1
        return f"{base} {suffix}"
