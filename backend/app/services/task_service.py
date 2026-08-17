"""Task service: the Task Engine's business logic (Sprint 19).

Sits between the API layer and the repository layer and owns every decision:
ownership, reference validation, the command state machine, and launching runs.
Repositories persist; this decides.

Mirrors :mod:`app.services.workflow_service` deliberately — same error
vocabulary, same ownership check, same unit-of-work responsibility — so the two
domains behave identically at their edges.

Nothing here executes a workflow itself. A task that launches one hands it to
the existing Sprint 18.6 :class:`WorkflowExecutionService` — the one
authoring↔runtime bridge — and records which run came back. There is exactly
one execution pipeline, and this service is a caller of it, not a second one.

Ownership is never re-implemented: the attached workflow is validated through
:class:`WorkflowService` and the assignee through :class:`EmployeeService`, so
"is this yours" keeps its single definition in each domain.
"""

import uuid
from typing import Any, Dict, Optional, Sequence, Tuple

from app.models.task import Task
from app.models.user import User
from app.models.workflow_execution import WorkflowExecution
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.notification_emitter import NotificationEmitter
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
    EmployeeService,
)
from app.services.workflow_execution_history_service import (
    TRIGGER_RETRY,
    STATUS_COMPLETED,
)
from app.services.workflow_execution_service import (
    TrackedExecution,
    WorkflowExecutionService,
)
from app.services.workflow_service import (
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowService,
)
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
    NotificationType,
    TaskStatus,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# How a duplicate names itself when the caller supplies nothing.
_COPY_SUFFIX = " (copy)"

#: The number the per-owner business-id series starts after (``TSK-1001`` …).
_BUSINESS_ID_BASE = 1000

#: Which commands a task in each status will accept — the same table the
#: frontend toolbar reads, owned here so a stale button can't drive an illegal
#: move. A task WAITING_APPROVAL takes no pause or resume (the approval is what
#: moves it); terminal states accept nothing but a retry, and COMPLETED not
#: even that.
ALLOWED_COMMANDS: Dict[str, Tuple[str, ...]] = {
    TaskStatus.PENDING.value: ("queue", "cancel"),
    TaskStatus.QUEUED.value: ("pause", "cancel"),
    TaskStatus.PLANNING.value: ("pause", "cancel"),
    TaskStatus.RUNNING.value: ("pause", "cancel"),
    TaskStatus.WAITING_APPROVAL.value: ("cancel",),
    TaskStatus.PAUSED.value: ("resume", "cancel"),
    TaskStatus.COMPLETED.value: (),
    TaskStatus.FAILED.value: ("retry", "cancel"),
    TaskStatus.CANCELLED.value: ("retry",),
    TaskStatus.BLOCKED.value: ("cancel",),
}

#: The status a command moves a task to.
COMMAND_RESULT: Dict[str, str] = {
    "queue": TaskStatus.QUEUED.value,
    "pause": TaskStatus.PAUSED.value,
    "resume": TaskStatus.RUNNING.value,
    "cancel": TaskStatus.CANCELLED.value,
    "retry": TaskStatus.QUEUED.value,
}

#: Statuses from which a task may launch its workflow. Waiting states are
#: excluded — an approval or a pause is a person's hold, and a launch must not
#: silently override it — and terminal states go through ``retry`` first.
_EXECUTABLE_STATUSES = frozenset(
    {
        TaskStatus.PENDING.value,
        TaskStatus.QUEUED.value,
        TaskStatus.PLANNING.value,
        TaskStatus.RUNNING.value,
    }
)


class TaskError(Exception):
    """Base class for task-related domain errors."""


class TaskNotFoundError(TaskError):
    """Raised when no task exists for the given identifier."""


class TaskAccessDeniedError(TaskError):
    """Raised when a task exists but is owned by another user."""


class TaskValidationError(TaskError):
    """Raised when a request would leave the task in an invalid state."""


class InvalidTaskCommandError(TaskError):
    """Raised when a command is not permitted from the task's current status."""


class TaskService:
    """Coordinates task operations using the repository layer.

    Constructed with the request-scoped session and, for endpoints that launch
    runs, the injected Sprint 18.6 :class:`WorkflowExecutionService`
    (constructor injection; it instantiates no coordinator). The service owns
    the unit of work: repositories ``flush`` while the service commits.
    """

    def __init__(
        self,
        session,
        execution_service: Optional[WorkflowExecutionService] = None,
        recorder: Optional[ActivityRecorder] = None,
        notifier: Optional[NotificationEmitter] = None,
    ) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.workflows = WorkflowService(session)
        self.employees = EmployeeService(session)
        self.execution_service = execution_service
        #: Optional cross-domain emission, injected by the DI factory so the API
        #: path feeds the platform timeline and inbox (Sprint 23). Left ``None``
        #: when this service is composed inside another (e.g. the conversation
        #: orchestrator), so an event is emitted once, by the outer owner.
        self.recorder = recorder
        self.notifier = notifier

    # --- Creation --------------------------------------------------------

    def create_task(self, owner: User, data: TaskCreate) -> Task:
        """Create a new task owned by ``owner`` and persist it.

        The workflow and employee references, when supplied, are validated
        through their own domains' ownership checks — a task can only point at
        things its owner could open themselves.
        """
        name = self._clean_name(data.name)
        workflow_id = self._validated_workflow_id(owner, data.workflow_id)
        employee_id = self._validated_employee_id(owner, data.employee_id)

        task = self.tasks.create(
            owner.id,
            business_id=self._next_business_id(owner),
            name=name,
            description=data.description,
            status=TaskStatus.PENDING.value,
            priority=data.priority.value,
            execution_mode=data.execution_mode.value,
            workflow_id=workflow_id,
            employee_id=employee_id,
        )
        self.session.commit()
        self.session.refresh(task)
        logger.info("User %s created task %s", owner.id, task.id)
        self._record(
            task,
            ActivityKind.CREATED,
            f"Created task {task.business_id}: {task.name}",
            actor_id=owner.id,
        )
        return task

    # --- Reads -----------------------------------------------------------

    def list_tasks(self, owner: User) -> Sequence[Task]:
        """Return all of ``owner``'s tasks."""
        return self.tasks.list_by_user(owner.id)

    def get_task(self, owner: User, task_id: uuid.UUID) -> Task:
        """Return a single task the ``owner`` is allowed to access.

        Raises :class:`TaskNotFoundError` if it does not exist, or
        :class:`TaskAccessDeniedError` if it belongs to another user.
        """
        task = self.tasks.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(str(task_id))
        if task.user_id != owner.id:
            logger.warning(
                "User %s attempted to access task %s owned by %s",
                owner.id,
                task_id,
                task.user_id,
            )
            raise TaskAccessDeniedError(str(task_id))
        return task

    # --- Update ----------------------------------------------------------

    def update_task(self, owner: User, task_id: uuid.UUID, data: TaskUpdate) -> Task:
        """Apply a partial update. Only supplied fields change.

        ``workflow_id`` and ``employee_id`` distinguish "clear it" (an explicit
        ``null``) from "leave it alone" (omitted) via ``model_fields_set`` —
        assignment, reassignment and unassignment are all this one operation.
        """
        task = self.get_task(owner, task_id)
        supplied = data.model_fields_set

        fields: dict[str, object] = {}

        if data.name is not None:
            fields["name"] = self._clean_name(data.name)
        if "description" in supplied:
            fields["description"] = data.description
        if data.priority is not None:
            fields["priority"] = data.priority.value
        if data.execution_mode is not None:
            fields["execution_mode"] = data.execution_mode.value

        if "workflow_id" in supplied:
            fields["workflow_id"] = self._validated_workflow_id(
                owner, data.workflow_id
            )
        if "employee_id" in supplied:
            fields["employee_id"] = self._validated_employee_id(
                owner, data.employee_id
            )

        if fields:
            self.tasks.update_fields(task, **fields)
            self.session.commit()
            self.session.refresh(task)
        return task

    # --- Duplicate -------------------------------------------------------

    def duplicate_task(
        self,
        owner: User,
        task_id: uuid.UUID,
        name: Optional[str] = None,
    ) -> Task:
        """Copy a task's description into a new pending task.

        A copy inherits the plan — description, priority, mode, references —
        never the run: it starts PENDING with no progress and no execution
        history, because it has done nothing.
        """
        source = self.get_task(owner, task_id)
        clone_name = self._clean_name(name) if name else f"{source.name}{_COPY_SUFFIX}"

        clone = self.tasks.create(
            owner.id,
            business_id=self._next_business_id(owner),
            name=clone_name,
            description=source.description,
            status=TaskStatus.PENDING.value,
            priority=source.priority,
            execution_mode=source.execution_mode,
            workflow_id=source.workflow_id,
            employee_id=source.employee_id,
        )
        self.session.commit()
        self.session.refresh(clone)
        logger.info("User %s duplicated task %s into %s", owner.id, source.id, clone.id)
        return clone

    # --- Commands --------------------------------------------------------

    def run_command(self, owner: User, task_id: uuid.UUID, command: str) -> Task:
        """Apply one state-machine command: queue, pause, resume, cancel, retry.

        The one command table decides legality — the same table the frontend
        toolbar disables buttons from, so a disabled button and a rejected
        request can never disagree. A retry or queue starts the story over:
        progress returns to zero because the previous run's progress isn't this
        run's.
        """
        task = self.get_task(owner, task_id)

        if command not in COMMAND_RESULT:
            raise TaskValidationError(f"{command!r} is not a task command.")

        if command not in ALLOWED_COMMANDS.get(task.status, ()):
            raise InvalidTaskCommandError(
                f"A task that's {self._status_label(task.status)} "
                f"can't be {command}d."
            )

        fields: dict[str, object] = {"status": COMMAND_RESULT[command]}
        if command in ("queue", "retry"):
            fields["progress"] = 0

        self.tasks.update_fields(task, **fields)
        self.session.commit()
        self.session.refresh(task)
        logger.info("User %s ran %s on task %s", owner.id, command, task.id)
        return task

    # --- Execution (the Workflow-platform bridge) ------------------------

    def execute_task(
        self,
        owner: User,
        task_id: uuid.UUID,
        *,
        initial_inputs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Task, TrackedExecution]:
        """Launch the task's workflow through the existing execution service.

        The run itself is entirely the Sprint 18.6 service's: ownership of the
        workflow, the published-only gate, translation, the runtime, and the
        history row all happen exactly as a direct workflow run would. This
        method adds only what is the task's to add — that the task may launch
        right now, the link to the recorded run, and the task's own status and
        progress reflecting how the run went.

        Raises :class:`TaskValidationError` when no workflow is attached, and
        :class:`InvalidTaskCommandError` when the task's status forbids a
        launch. The execution service's own refusals (not published,
        untranslatable) propagate unchanged, so a task run refuses in exactly
        the words a workflow run does.
        """
        task = self.get_task(owner, task_id)
        execution_service = self._require_execution_service()

        if task.workflow_id is None:
            raise TaskValidationError(
                "This task has no workflow attached. Attach one first."
            )
        if task.status not in _EXECUTABLE_STATUSES:
            raise InvalidTaskCommandError(
                f"A task that's {self._status_label(task.status)} can't be run."
            )

        # The launch is handed to the one existing pipeline. A refusal raises
        # before anything runs and this task is left exactly as it was.
        tracked = execution_service.execute_and_record(
            owner,
            task.workflow_id,
            initial_inputs=initial_inputs or None,
        )

        self._record_run(task, tracked.execution)
        logger.info(
            "Task %s launched execution %s: %s",
            task.id,
            tracked.execution.id,
            tracked.execution.status,
        )
        return task, tracked

    def retry_execution(
        self,
        owner: User,
        task_id: uuid.UUID,
        execution_id: uuid.UUID,
    ) -> Tuple[Task, TrackedExecution]:
        """Run the task's workflow again, repeating one of the task's own runs.

        Composes the same collaborators the workflow-executions retry endpoint
        does — history for the original, the execution service for the new run
        — plus the task's own bookkeeping. The original run is never touched;
        the new one points back at it, exactly as every retry does.

        The run being repeated must be one this task launched: retrying
        another task's (or no task's) run from here would misfile the result.
        """
        task = self.get_task(owner, task_id)
        execution_service = self._require_execution_service()

        link = self.tasks.get_link_for_execution(execution_id)
        if link is None or link.task_id != task.id:
            raise TaskNotFoundError(str(execution_id))

        if task.status == TaskStatus.COMPLETED.value:
            # A completed task accepts no commands, and a retry is one.
            raise InvalidTaskCommandError(
                "A completed task can't be re-run. Duplicate it instead."
            )

        tracked = execution_service.execute_and_record(
            owner,
            # The workflow the original run belongs to — the task's workflow may
            # have been swapped since, and a retry repeats what ran, not what
            # would run now.
            link.execution.workflow_id,
            trigger=TRIGGER_RETRY,
            retry_of_execution_id=execution_id,
        )

        self._record_run(task, tracked.execution)
        logger.info(
            "Task %s retried execution %s as %s",
            task.id,
            execution_id,
            tracked.execution.id,
        )
        return task, tracked

    def list_executions(
        self,
        owner: User,
        task_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[Sequence[WorkflowExecution], int]:
        """The runs this task launched, newest first, with the total count."""
        self.get_task(owner, task_id)  # ownership, reused
        rows = self.tasks.list_executions(task_id, skip=skip, limit=limit)
        return rows, self.tasks.count_executions(task_id)

    def execution_overview(
        self, task: Task
    ) -> Tuple[Optional[WorkflowExecution], int]:
        """The task's newest run and how many there have been.

        Takes an already-loaded task rather than an id: every caller reached
        the task through :meth:`get_task`, so ownership is already decided and
        deciding it again here would just run the same query twice.
        """
        return (
            self.tasks.latest_execution(task.id),
            self.tasks.count_executions(task.id),
        )

    # --- Internals -------------------------------------------------------

    def _record_run(self, task: Task, execution: WorkflowExecution) -> None:
        """Link a recorded run to its task and reflect how it went.

        Called after ``execute_and_record`` has already committed the history
        row — history's transaction is its own, untouched. This second, small
        commit covers only the task's side: the link, the status, and the
        progress the run reported.
        """
        self.tasks.add_execution_link(task.id, execution.id)

        completed = execution.status == STATUS_COMPLETED
        progress = _percent(
            execution.completed_step_count, execution.total_step_count
        )
        self.tasks.update_fields(
            task,
            status=(
                TaskStatus.COMPLETED.value if completed else TaskStatus.FAILED.value
            ),
            progress=progress,
        )
        self.session.commit()
        self.session.refresh(task)

        if completed:
            self._record(
                task,
                ActivityKind.COMPLETED,
                f"Run completed ({progress}%)",
                actor_id=task.user_id,
            )
        else:
            self._record(
                task,
                ActivityKind.UPDATED,
                f"Run failed at {progress}%",
                actor_id=task.user_id,
            )
            # A failed run is worth an inbox entry even when the owner launched
            # it, so it is attributed to the platform (no human actor) rather
            # than suppressed as a self-notification.
            self._notify(
                task,
                "A task run failed",
                f"{task.business_id} didn't finish. Open it to review and retry.",
                actor_type=ActivityActorType.SYSTEM,
                actor_id=None,
            )

    # --- Cross-domain emission (best-effort) -----------------------------

    def _record(
        self,
        task: Task,
        kind: ActivityKind,
        summary: str,
        *,
        actor_id: Optional[uuid.UUID],
        actor_type: ActivityActorType = ActivityActorType.USER,
    ) -> None:
        """Append one task-timeline event when a recorder is attached."""
        if self.recorder is None:
            return
        self.recorder.record(
            CollaborationResourceType.TASK,
            task.id,
            kind,
            summary,
            actor_type=actor_type,
            actor_id=actor_id,
            owner_user_id=task.user_id,
        )

    def _notify(
        self,
        task: Task,
        title: str,
        description: str,
        *,
        actor_type: ActivityActorType,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Raise an inbox notification for the task's owner (best-effort).

        Never notifies someone of their own action: an actor who is the owner is
        skipped, so only work done *for* the owner (by an AI employee or the
        platform) reaches the inbox.
        """
        if self.notifier is None:
            return
        if actor_id is not None and actor_id == task.user_id:
            return
        self.notifier.emit(
            task.user_id,
            NotificationType.TASK,
            title,
            description,
            resource_type=CollaborationResourceType.TASK,
            resource_id=task.id,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def _require_execution_service(self) -> WorkflowExecutionService:
        if self.execution_service is None:  # pragma: no cover - wiring guarantees one
            raise RuntimeError("This service was built without workflow execution.")
        return self.execution_service

    def _validated_workflow_id(
        self, owner: User, workflow_id: Optional[uuid.UUID]
    ) -> Optional[uuid.UUID]:
        """A workflow reference the owner is allowed to make, or ``None``.

        Existence and ownership come from :class:`WorkflowService` — the one
        definition of "your workflow". Its errors are translated into this
        domain's validation vocabulary because from the task's side a bad
        reference is a bad request, not a missing task.
        """
        if workflow_id is None:
            return None
        try:
            self.workflows.get_workflow(owner, workflow_id)
        except (WorkflowNotFoundError, WorkflowAccessDeniedError) as exc:
            raise TaskValidationError("That workflow doesn't exist.") from exc
        return workflow_id

    def _validated_employee_id(
        self, owner: User, employee_id: Optional[uuid.UUID]
    ) -> Optional[uuid.UUID]:
        """An employee reference the owner is allowed to make, or ``None``."""
        if employee_id is None:
            return None
        try:
            self.employees.get_employee(owner, employee_id)
        except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
            raise TaskValidationError("That employee doesn't exist.") from exc
        return employee_id

    def _next_business_id(self, owner: User) -> str:
        """``TSK-1001``, ``TSK-1002``… — sequential per owner, never reused."""
        return f"TSK-{_BUSINESS_ID_BASE + self.tasks.count_by_user(owner.id) + 1}"

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise TaskValidationError("A task needs a name.")
        return cleaned

    @staticmethod
    def _status_label(status: str) -> str:
        """The status as a person reads it (``waiting_approval`` → ``waiting approval``)."""
        return status.replace("_", " ")


def _percent(completed: int, total: int) -> int:
    """Whole-number progress, safe when a run had no steps."""
    if total <= 0:
        return 0
    return max(0, min(100, round(completed * 100 / total)))
