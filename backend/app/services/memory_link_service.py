"""Memory link service: integrate existing memories with tasks and workflows.

Sits between the API layer and the repository layer and owns the integration's
decisions — which memory a user may reference, from which task or workflow — by
*reusing* every existing ownership chain rather than re-implementing one:

* the memory's owner comes from the Memory → Employee → User chain, via
  :class:`EmployeeService` (the same call the Memory Engine uses);
* the task's owner comes from :class:`TaskService`;
* the workflow's owner comes from :class:`WorkflowService`.

A user can only link a memory to a task/workflow when the same user owns all
three, so an integration never becomes a back door into another user's data.
Nothing here creates, edits, embeds, ranks, or retrieves memory content — the
Sprint 2 Memory Engine remains the sole owner of that. This service adds only
the associations (link rows over existing memories) and the user-wide read that
lets a memory be found across all of a user's employees.
"""

import uuid
from typing import Optional, Sequence, Tuple

from app.models.memory import Memory
from app.models.user import User
from app.repositories.memory_link_repository import MemoryLinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
    EmployeeService,
)
from app.services.task_service import TaskService
from app.services.workflow_service import WorkflowService
from app.utils.constants import MemoryType
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryLinkError(Exception):
    """Base class for memory-integration domain errors."""


class MemoryReferenceError(MemoryLinkError):
    """Raised when a referenced memory doesn't exist or isn't the user's.

    A bad memory reference is a bad request from the caller's side, so it reads
    as "not found" rather than leaking whether the memory exists for someone
    else — the same stance the task and workflow reference checks take.
    """


class MemoryLinkNotFoundError(MemoryLinkError):
    """Raised when detaching a memory that the task/workflow doesn't reference."""


class MemoryLinkService:
    """Coordinates memory ↔ task/workflow links and user-wide memory reads.

    Composes the existing services and repositories in its constructor and owns
    the unit of work: repositories ``flush`` while this service commits. The
    :class:`TaskService` is built without an execution service — linking never
    launches a run, and ``get_task`` needs none.
    """

    # Hard ceiling on how many memories a single user-wide read may return,
    # matching the Memory Engine's own safeguard.
    MAX_LIMIT = 100

    def __init__(self, session) -> None:
        self.session = session
        self.links = MemoryLinkRepository(session)
        self.memories = MemoryRepository(session)
        self.employees = EmployeeService(session)
        self.tasks = TaskService(session)
        self.workflows = WorkflowService(session)

    # --- Task ↔ memory ---------------------------------------------------

    def list_task_memories(
        self, owner: User, task_id: uuid.UUID
    ) -> Sequence[Tuple[Memory, str]]:
        """The memories a task references. Ownership of the task is checked."""
        self.tasks.get_task(owner, task_id)  # 404 / 403 propagate
        return self.links.list_task_memories(task_id)

    def attach_memory_to_task(
        self, owner: User, task_id: uuid.UUID, memory_id: uuid.UUID
    ) -> Tuple[Memory, str]:
        """Reference an existing memory from a task.

        Both the task and the memory must belong to ``owner``. Idempotent: a
        memory already referenced by the task is returned unchanged rather than
        duplicated.
        """
        self.tasks.get_task(owner, task_id)
        memory, employee_name = self._owned_memory(owner, memory_id)

        if self.links.get_task_link(task_id, memory.id) is None:
            self.links.add_task_link(task_id, memory.id)
            self.session.commit()
            logger.info(
                "User %s linked memory %s to task %s", owner.id, memory.id, task_id
            )
        return memory, employee_name

    def detach_memory_from_task(
        self, owner: User, task_id: uuid.UUID, memory_id: uuid.UUID
    ) -> None:
        """Remove a task's reference to a memory. The memory itself is untouched."""
        self.tasks.get_task(owner, task_id)
        link = self.links.get_task_link(task_id, memory_id)
        if link is None:
            raise MemoryLinkNotFoundError(str(memory_id))
        self.links.delete_task_link(link)
        self.session.commit()
        logger.info(
            "User %s unlinked memory %s from task %s", owner.id, memory_id, task_id
        )

    # --- Workflow ↔ memory -----------------------------------------------

    def list_workflow_memories(
        self, owner: User, workflow_id: uuid.UUID
    ) -> Sequence[Tuple[Memory, str]]:
        """The memories a workflow references. Ownership of the workflow is checked."""
        self.workflows.get_workflow(owner, workflow_id)  # 404 / 403 propagate
        return self.links.list_workflow_memories(workflow_id)

    def attach_memory_to_workflow(
        self, owner: User, workflow_id: uuid.UUID, memory_id: uuid.UUID
    ) -> Tuple[Memory, str]:
        """Reference an existing memory from a workflow. Same rules as the task side."""
        self.workflows.get_workflow(owner, workflow_id)
        memory, employee_name = self._owned_memory(owner, memory_id)

        if self.links.get_workflow_link(workflow_id, memory.id) is None:
            self.links.add_workflow_link(workflow_id, memory.id)
            self.session.commit()
            logger.info(
                "User %s linked memory %s to workflow %s",
                owner.id,
                memory.id,
                workflow_id,
            )
        return memory, employee_name

    def detach_memory_from_workflow(
        self, owner: User, workflow_id: uuid.UUID, memory_id: uuid.UUID
    ) -> None:
        """Remove a workflow's reference to a memory."""
        self.workflows.get_workflow(owner, workflow_id)
        link = self.links.get_workflow_link(workflow_id, memory_id)
        if link is None:
            raise MemoryLinkNotFoundError(str(memory_id))
        self.links.delete_workflow_link(link)
        self.session.commit()
        logger.info(
            "User %s unlinked memory %s from workflow %s",
            owner.id,
            memory_id,
            workflow_id,
        )

    # --- User-wide read / search (the shared-resource access) ------------

    def search_memories(
        self,
        owner: User,
        *,
        keyword: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        min_importance: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[Sequence[Tuple[Memory, str]], int]:
        """A user's memories across all their employees, with the total.

        This is the shared-resource read the Memory Engine never exposed: a
        memory addressable by its owning *user* rather than only through a named
        employee. ``keyword`` searches memory content; the other filters reuse
        the Engine's own semantics. ``limit`` is capped defensively.
        """
        capped = min(limit, self.MAX_LIMIT)
        rows = self.links.search_user_memories(
            owner.id,
            keyword=keyword.strip() if keyword and keyword.strip() else None,
            memory_type=memory_type.value if memory_type is not None else None,
            min_importance=min_importance,
            limit=capped,
            offset=offset,
        )
        total = self.links.count_user_memories(owner.id)
        return rows, total

    # --- Internals -------------------------------------------------------

    def _owned_memory(
        self, owner: User, memory_id: uuid.UUID
    ) -> Tuple[Memory, str]:
        """Load a memory the ``owner`` is allowed to reference, with owner name.

        Existence comes from the repository; ownership comes from the memory's
        Employee → User chain via :class:`EmployeeService` — the one definition
        of "your memory". Any miss is translated into this domain's reference
        error, because from the caller's side a memory they can't reference is a
        bad request, not a missing task.
        """
        memory = self.memories.get_memory(memory_id)
        if memory is None:
            raise MemoryReferenceError(str(memory_id))
        try:
            employee = self.employees.get_employee(owner, memory.employee_id)
        except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
            raise MemoryReferenceError(str(memory_id)) from exc
        return memory, employee.name
