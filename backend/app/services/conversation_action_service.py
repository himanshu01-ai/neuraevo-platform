"""Conversation action service — the backend conversation orchestrator (Sprint 23).

The single place a *confirmed* conversational action becomes real work. It
composes the services the platform already has rather than adding a second
pipeline:

    ConversationService  (reused ownership: whose conversation, which employee)
        ↓
    TaskService          (reused creation: the one Task Engine)
        ↓
    ActivityRecorder     (the cross-domain timeline seam)
    NotificationEmitter  (the cross-domain inbox seam)

Before this, a task the assistant offered to create was made by a detached
frontend call: it was owned by the user but carried by *no* employee, linked to
*no* conversation, and left *no* trace on the timeline or in the inbox. This
service closes that gap. The task it creates is carried by the conversation's
employee — the AI that proposed it — and its creation is recorded on both the
task's and the conversation's timelines and announced in the owner's inbox, with
the employee as the actor. The confirmation gate stays where it belongs: this
runs only after the user has approved the action.

It composes a *silent* :class:`TaskService` (no recorder/notifier of its own) so
the task-created event is emitted once, here, as an employee action — never
twice, and never mis-attributed to the user.
"""

import uuid
from typing import Optional

from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate
from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.notification_emitter import NotificationEmitter
from app.services.conversation_service import ConversationService
from app.services.task_service import TaskService
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
    NotificationType,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

#: The longest task name a confirmed action produces before it is trimmed.
_MAX_NAME = 255


class ConversationActionService:
    """Turns a confirmed conversation action into a linked, announced task.

    Owns no unit of work of its own beyond what its collaborators commit: the
    task service commits the task, and the recorder/emitter each commit their
    own best-effort write. Ownership is never re-decided here — it is the reused
    :class:`ConversationService` chain (the conversation's employee must belong
    to the caller), and the task inherits that same owner.
    """

    def __init__(
        self,
        session,
        task_service: Optional[TaskService] = None,
        recorder: Optional[ActivityRecorder] = None,
        notifier: Optional[NotificationEmitter] = None,
    ) -> None:
        self.session = session
        # Reused for ownership + resolving the employee behind the conversation.
        self.conversations = ConversationService(session)
        # A silent task service: it must not emit its own (user-attributed)
        # task-created event, because this orchestrator emits an
        # employee-attributed one. Falls back to a bare service for tests.
        self.tasks = task_service or TaskService(session)
        self.recorder = recorder
        self.notifier = notifier

    def create_task_from_conversation(
        self,
        owner: User,
        conversation_id: uuid.UUID,
        label: str,
        summary: str,
    ) -> Task:
        """Create a task for a confirmed action and link + announce it.

        Raises :class:`ConversationNotFoundError` (reused) when the conversation
        is not the caller's, before anything is created. On success the task is
        carried by the conversation's employee, recorded on both timelines, and
        announced in the owner's inbox as the employee's doing.
        """
        conversation = self.conversations.get_for_user(owner, conversation_id)
        employee = conversation.employee
        employee_id = conversation.employee_id
        employee_name = employee.name if employee is not None else "your assistant"

        task = self.tasks.create_task(
            owner,
            TaskCreate(
                name=self._name(label, summary),
                description=(
                    f"Created from a conversation with {employee_name}."
                ),
                employee_id=employee_id,
            ),
        )

        logger.info(
            "Conversation %s created task %s (employee %s) from an approved action",
            conversation_id,
            task.id,
            employee_id,
        )

        self._record(
            CollaborationResourceType.TASK,
            task.id,
            ActivityKind.CREATED,
            f"{employee_name} created this from a conversation",
            owner_user_id=owner.id,
            actor_id=employee_id,
        )
        self._record(
            CollaborationResourceType.CONVERSATION,
            conversation_id,
            ActivityKind.ASSIGNED,
            f"Created task {task.business_id}: {task.name}",
            owner_user_id=owner.id,
            actor_id=employee_id,
        )
        self._notify(
            owner.id,
            "Your assistant created a task",
            f"{employee_name} created {task.business_id}: {task.name}",
            task_id=task.id,
            actor_id=employee_id,
        )
        return task

    # --- Cross-domain emission (best-effort) -----------------------------

    def _record(
        self,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        kind: ActivityKind,
        summary: str,
        *,
        owner_user_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Append one timeline event, as the employee, when a recorder exists."""
        if self.recorder is None:
            return
        self.recorder.record(
            resource_type,
            resource_id,
            kind,
            summary,
            actor_type=ActivityActorType.EMPLOYEE,
            actor_id=actor_id,
            owner_user_id=owner_user_id,
        )

    def _notify(
        self,
        recipient_user_id: uuid.UUID,
        title: str,
        description: str,
        *,
        task_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Announce the task in the owner's inbox, as the employee's doing."""
        if self.notifier is None:
            return
        self.notifier.emit(
            recipient_user_id,
            NotificationType.TASK,
            title,
            description,
            resource_type=CollaborationResourceType.TASK,
            resource_id=task_id,
            actor_type=ActivityActorType.EMPLOYEE,
            actor_id=actor_id,
        )

    @staticmethod
    def _name(label: str, summary: str) -> str:
        """A task name from the action, trimmed to the column's limit."""
        name = f"{label.strip()}: {summary.strip()}".strip(": ").strip()
        if len(name) > _MAX_NAME:
            name = name[: _MAX_NAME - 1].rstrip() + "…"
        return name
