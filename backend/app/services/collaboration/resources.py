"""Owner-agnostic resolution of a collaboration resource (Sprint 20).

Collaboration is polymorphic over four resources, and each already knows who
owns it. This resolver reads that owner back through the resource's *existing*
chain — ``Task``/``Workflow`` carry a ``user_id``; ``Conversation``/``Memory``
reach a user through their employee — without re-implementing an ownership rule.

Why it reads through repositories rather than the domains' owner-scoped service
getters: those getters answer "does *this* user own it?" and refuse anyone
else, but access resolution must succeed for a *participant* who is not the
owner. So the resolver loads the row and reports its owner id, and the
:class:`~app.services.collaboration.service.CollaborationService` makes the
access decision in one place. Reading the owner id is not an ownership decision;
comparing it to a caller is, and that lives in exactly one service.
"""

import uuid
from dataclasses import dataclass
from typing import Optional, Union

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.utils.constants import CollaborationResourceType


@dataclass(frozen=True)
class ResourceRef:
    """A resolved resource and the user that owns it."""

    resource_type: CollaborationResourceType
    resource_id: uuid.UUID
    owner_user_id: uuid.UUID


class ResourceResolver:
    """Loads a collaboration resource and reports its owning user.

    Persistence-only reads composed here; no access decision is made. Returns
    ``None`` when the resource does not exist, so the caller can map a missing
    resource to a not-found response without this layer knowing about HTTP.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.workflows = WorkflowRepository(session)
        self.conversations = ConversationRepository(session)
        self.memories = MemoryRepository(session)
        self.employees = EmployeeRepository(session)

    def load(
        self,
        resource_type: Union[CollaborationResourceType, str],
        resource_id: uuid.UUID,
    ) -> Optional[ResourceRef]:
        """Resolve a resource to its owner, or ``None`` if it does not exist."""
        rt = CollaborationResourceType(resource_type)

        owner_id: Optional[uuid.UUID]
        if rt is CollaborationResourceType.TASK:
            task = self.tasks.get_by_id(resource_id)
            owner_id = task.user_id if task is not None else None
        elif rt is CollaborationResourceType.WORKFLOW:
            workflow = self.workflows.get_by_id(resource_id)
            owner_id = workflow.user_id if workflow is not None else None
        elif rt is CollaborationResourceType.CONVERSATION:
            conversation = self.conversations.get(resource_id)
            owner_id = (
                self._employee_owner(conversation.employee_id)
                if conversation is not None
                else None
            )
        else:  # MEMORY
            memory = self.memories.get_memory(resource_id)
            owner_id = (
                self._employee_owner(memory.employee_id)
                if memory is not None
                else None
            )

        if owner_id is None:
            return None
        return ResourceRef(
            resource_type=rt, resource_id=resource_id, owner_user_id=owner_id
        )

    def _employee_owner(self, employee_id: uuid.UUID) -> Optional[uuid.UUID]:
        """The user behind an employee, resolved even if the employee is retired.

        ``include_deleted`` because a soft-deleted employee still preserves the
        conversations and memories hanging off it (see ``Employee.deleted_at``),
        and those still belong to the same user for access purposes.
        """
        employee = self.employees.get_by_id(employee_id, include_deleted=True)
        return employee.user_id if employee is not None else None
