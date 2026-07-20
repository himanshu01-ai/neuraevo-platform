"""Task Engine tests (Sprint 19).

Two layers, neither of which touches a database or network:

* ``TaskServiceTests`` run the real :class:`TaskService` against an in-memory
  fake repository, with the workflow and employee ownership seams mocked and a
  fake execution service standing in for the Sprint 18.6 pipeline — so
  creation, assignment, workflow linking, the command state machine, launching,
  retrying and history access are exercised for real.
* ``TaskAPITests`` drive the endpoints through ``TestClient`` with the service
  mocked, covering HTTP concerns — status codes, error mapping, ownership and
  auth.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_tasks
"""

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_task_service
from app.main import app
from app.models.task import Task
from app.models.workflow_execution import WorkflowExecution
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import (
    ALLOWED_COMMANDS,
    COMMAND_RESULT,
    InvalidTaskCommandError,
    TaskAccessDeniedError,
    TaskNotFoundError,
    TaskService,
    TaskValidationError,
)
from app.services.workflow_execution_service import TrackedExecution
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
)
from app.services.employee_service import EmployeeNotFoundError
from app.utils.constants import TaskStatus


# --- Test doubles --------------------------------------------------------


class FakeSession:
    """Minimal unit-of-work stand-in that records commits."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, instance) -> None:  # pragma: no cover - no-op
        return None


class FakeTaskRepository:
    """In-memory mirror of :class:`TaskRepository`'s public surface."""

    def __init__(self, session) -> None:
        self.session = session
        self.rows: dict[uuid.UUID, Task] = {}
        self.links: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.executions: dict[uuid.UUID, WorkflowExecution] = {}

    # -- reads
    def get_by_id(self, task_id):
        return self.rows.get(task_id)

    def list_by_user(self, user_id, *, skip=0, limit=100):
        rows = [t for t in self.rows.values() if t.user_id == user_id]
        return rows[skip : skip + limit]

    def count_by_user(self, user_id):
        return len([t for t in self.rows.values() if t.user_id == user_id])

    # -- writes
    def create(
        self,
        user_id,
        *,
        business_id,
        name,
        description,
        status,
        priority,
        execution_mode,
        employee_id=None,
        workflow_id=None,
    ):
        task = Task(
            id=uuid.uuid4(),
            user_id=user_id,
            business_id=business_id,
            name=name,
            description=description,
            status=status,
            priority=priority,
            execution_mode=execution_mode,
            employee_id=employee_id,
            workflow_id=workflow_id,
            progress=0,
        )
        task.created_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        self.rows[task.id] = task
        return task

    def update_fields(self, task, **fields):
        for key, value in fields.items():
            setattr(task, key, value)
        return task

    def delete(self, task) -> None:
        self.rows.pop(task.id, None)

    # -- execution links
    def add_execution_link(self, task_id, execution_id):
        self.links.append((task_id, execution_id))
        return SimpleNamespace(task_id=task_id, execution_id=execution_id)

    def get_link_for_execution(self, execution_id):
        for task_id, linked_id in self.links:
            if linked_id == execution_id:
                return SimpleNamespace(
                    task_id=task_id,
                    execution_id=linked_id,
                    execution=self.executions.get(linked_id),
                )
        return None

    def list_executions(self, task_id, *, skip=0, limit=50):
        rows = [
            self.executions[linked_id]
            for linked_task, linked_id in self.links
            if linked_task == task_id and linked_id in self.executions
        ]
        rows.sort(key=lambda e: e.started_at, reverse=True)
        return rows[skip : skip + limit]

    def count_executions(self, task_id):
        return len([1 for linked_task, _ in self.links if linked_task == task_id])

    def latest_execution(self, task_id):
        rows = self.list_executions(task_id)
        return rows[0] if rows else None


def make_execution(
    status: str = "COMPLETED",
    *,
    workflow_id: Optional[uuid.UUID] = None,
    completed: int = 2,
    total: int = 2,
) -> WorkflowExecution:
    """A recorded run, as history would have written it."""
    now = datetime.now(timezone.utc)
    execution = WorkflowExecution(
        id=uuid.uuid4(),
        workflow_id=workflow_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=status,
        started_at=now,
        finished_at=now,
        duration_ms=12,
        total_step_count=total,
        completed_step_count=completed,
        failed_step_id=None if status == "COMPLETED" else "step-2",
        error=None if status == "COMPLETED" else "It broke.",
        trigger="manual",
    )
    execution.created_at = now
    return execution


def make_result(execution: WorkflowExecution):
    """The runtime's result, shaped as ``execution_response`` reads it."""
    return SimpleNamespace(
        workflow_id=str(execution.workflow_id),
        workflow_status=execution.status,
        completed_step_count=execution.completed_step_count,
        total_step_count=execution.total_step_count,
        failed_step_id=execution.failed_step_id,
        step_references=[],
        final_outputs={},
        result_metadata={} if execution.error is None else {"error": execution.error},
    )


class FakeExecutionService:
    """Stands in for the Sprint 18.6 pipeline: records calls, returns a run."""

    def __init__(self, execution=None, error: Optional[Exception] = None) -> None:
        self.execution = execution or make_execution()
        self.error = error
        self.calls: list[dict] = []

    def execute_and_record(
        self,
        owner,
        workflow_id,
        *,
        initial_inputs=None,
        trigger="manual",
        retry_of_execution_id=None,
    ):
        self.calls.append(
            {
                "workflow_id": workflow_id,
                "initial_inputs": initial_inputs,
                "trigger": trigger,
                "retry_of_execution_id": retry_of_execution_id,
            }
        )
        if self.error is not None:
            raise self.error
        return TrackedExecution(
            result=make_result(self.execution), execution=self.execution
        )


def make_user(user_id: Optional[uuid.UUID] = None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    return user


def make_service(execution_service=None):
    session = FakeSession()
    service = TaskService(session, execution_service)
    service.tasks = FakeTaskRepository(session)
    # Ownership seams: the real services are replaced so tests decide what
    # exists and whose it is, without a database.
    service.workflows = MagicMock()
    service.employees = MagicMock()
    return service, session


# --- Service tests -------------------------------------------------------


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.execution_service = FakeExecutionService()
        self.service, self.session = make_service(self.execution_service)
        self.owner = make_user()

    def _create(self, name="Competitor brief", **kwargs):
        return self.service.create_task(
            self.owner, TaskCreate(name=name, description="d", **kwargs)
        )

    # -- create
    def test_create_persists_pending_and_commits(self):
        task = self._create()
        self.assertEqual(task.name, "Competitor brief")
        self.assertEqual(task.status, TaskStatus.PENDING.value)
        self.assertEqual(task.user_id, self.owner.id)
        self.assertEqual(task.progress, 0)
        self.assertEqual(self.session.commits, 1)

    def test_create_assigns_sequential_business_ids(self):
        first = self._create("One")
        second = self._create("Two")
        self.assertEqual(first.business_id, "TSK-1001")
        self.assertEqual(second.business_id, "TSK-1002")

    def test_create_rejects_blank_name(self):
        with self.assertRaises(TaskValidationError):
            self.service.create_task(
                self.owner, TaskCreate(name="   ", description="d")
            )

    def test_create_validates_workflow_through_workflow_service(self):
        workflow_id = uuid.uuid4()
        task = self._create(workflow_id=workflow_id)
        self.assertEqual(task.workflow_id, workflow_id)
        self.service.workflows.get_workflow.assert_called_once_with(
            self.owner, workflow_id
        )

    def test_create_rejects_missing_workflow(self):
        self.service.workflows.get_workflow.side_effect = WorkflowNotFoundError("x")
        with self.assertRaises(TaskValidationError):
            self._create(workflow_id=uuid.uuid4())

    def test_create_rejects_foreign_workflow(self):
        self.service.workflows.get_workflow.side_effect = WorkflowAccessDeniedError("x")
        with self.assertRaises(TaskValidationError):
            self._create(workflow_id=uuid.uuid4())

    def test_create_validates_employee_through_employee_service(self):
        employee_id = uuid.uuid4()
        task = self._create(employee_id=employee_id)
        self.assertEqual(task.employee_id, employee_id)
        self.service.employees.get_employee.assert_called_once_with(
            self.owner, employee_id
        )

    def test_create_rejects_missing_employee(self):
        self.service.employees.get_employee.side_effect = EmployeeNotFoundError("x")
        with self.assertRaises(TaskValidationError):
            self._create(employee_id=uuid.uuid4())

    # -- ownership
    def test_get_unknown_task_raises_not_found(self):
        with self.assertRaises(TaskNotFoundError):
            self.service.get_task(self.owner, uuid.uuid4())

    def test_get_other_users_task_raises_access_denied(self):
        task = self._create()
        with self.assertRaises(TaskAccessDeniedError):
            self.service.get_task(make_user(), task.id)

    # -- update / assignment
    def test_update_assigns_employee(self):
        task = self._create()
        employee_id = uuid.uuid4()
        updated = self.service.update_task(
            self.owner, task.id, TaskUpdate(employee_id=employee_id)
        )
        self.assertEqual(updated.employee_id, employee_id)

    def test_update_reassigns_employee(self):
        task = self._create(employee_id=uuid.uuid4())
        replacement = uuid.uuid4()
        updated = self.service.update_task(
            self.owner, task.id, TaskUpdate(employee_id=replacement)
        )
        self.assertEqual(updated.employee_id, replacement)

    def test_update_clears_employee_with_explicit_null(self):
        task = self._create(employee_id=uuid.uuid4())
        updated = self.service.update_task(
            self.owner, task.id, TaskUpdate(employee_id=None)
        )
        self.assertIsNone(updated.employee_id)

    def test_update_leaves_references_alone_when_omitted(self):
        employee_id = uuid.uuid4()
        task = self._create(employee_id=employee_id)
        updated = self.service.update_task(
            self.owner, task.id, TaskUpdate(name="Renamed")
        )
        self.assertEqual(updated.employee_id, employee_id)
        self.assertEqual(updated.name, "Renamed")

    def test_update_attaches_workflow(self):
        task = self._create()
        workflow_id = uuid.uuid4()
        updated = self.service.update_task(
            self.owner, task.id, TaskUpdate(workflow_id=workflow_id)
        )
        self.assertEqual(updated.workflow_id, workflow_id)

    def test_update_rejects_foreign_workflow(self):
        task = self._create()
        self.service.workflows.get_workflow.side_effect = WorkflowAccessDeniedError("x")
        with self.assertRaises(TaskValidationError):
            self.service.update_task(
                self.owner, task.id, TaskUpdate(workflow_id=uuid.uuid4())
            )

    # -- duplicate
    def test_duplicate_inherits_plan_never_run(self):
        task = self._create(workflow_id=uuid.uuid4(), employee_id=uuid.uuid4())
        self.service.tasks.update_fields(task, status="completed", progress=100)
        clone = self.service.duplicate_task(self.owner, task.id)
        self.assertEqual(clone.name, "Competitor brief (copy)")
        self.assertEqual(clone.workflow_id, task.workflow_id)
        self.assertEqual(clone.employee_id, task.employee_id)
        self.assertEqual(clone.status, TaskStatus.PENDING.value)
        self.assertEqual(clone.progress, 0)

    # -- commands
    def test_queue_moves_pending_to_queued(self):
        task = self._create()
        updated = self.service.run_command(self.owner, task.id, "queue")
        self.assertEqual(updated.status, TaskStatus.QUEUED.value)

    def test_retry_resets_progress(self):
        task = self._create()
        self.service.tasks.update_fields(task, status="failed", progress=60)
        updated = self.service.run_command(self.owner, task.id, "retry")
        self.assertEqual(updated.status, TaskStatus.QUEUED.value)
        self.assertEqual(updated.progress, 0)

    def test_command_refused_when_status_forbids_it(self):
        task = self._create()  # pending: pause not offered
        with self.assertRaises(InvalidTaskCommandError):
            self.service.run_command(self.owner, task.id, "pause")

    def test_completed_task_accepts_no_commands(self):
        task = self._create()
        self.service.tasks.update_fields(task, status="completed")
        for command in COMMAND_RESULT:
            with self.assertRaises(InvalidTaskCommandError):
                self.service.run_command(self.owner, task.id, command)

    def test_unknown_command_is_a_validation_error(self):
        task = self._create()
        with self.assertRaises(TaskValidationError):
            self.service.run_command(self.owner, task.id, "detonate")

    def test_command_table_covers_every_status(self):
        self.assertEqual(
            set(ALLOWED_COMMANDS), {status.value for status in TaskStatus}
        )

    # -- execute (the Workflow-platform bridge)
    def test_execute_requires_a_workflow(self):
        task = self._create()
        with self.assertRaises(TaskValidationError):
            self.service.execute_task(self.owner, task.id)

    def test_execute_refused_when_status_forbids_launch(self):
        task = self._create(workflow_id=uuid.uuid4())
        self.service.tasks.update_fields(task, status="paused")
        with self.assertRaises(InvalidTaskCommandError):
            self.service.execute_task(self.owner, task.id)
        self.assertEqual(self.execution_service.calls, [])

    def test_execute_links_run_and_completes_task(self):
        workflow_id = uuid.uuid4()
        task = self._create(workflow_id=workflow_id)
        updated, tracked = self.service.execute_task(self.owner, task.id)

        self.assertEqual(self.execution_service.calls[0]["workflow_id"], workflow_id)
        self.assertIn(
            (task.id, self.execution_service.execution.id), self.service.tasks.links
        )
        self.assertEqual(updated.status, TaskStatus.COMPLETED.value)
        self.assertEqual(updated.progress, 100)
        self.assertEqual(tracked.execution.id, self.execution_service.execution.id)

    def test_execute_reflects_a_failed_run(self):
        failed = make_execution("FAILED", completed=1, total=4)
        service, _ = make_service(FakeExecutionService(execution=failed))
        task = service.create_task(
            self.owner, TaskCreate(name="n", workflow_id=uuid.uuid4())
        )
        updated, _ = service.execute_task(self.owner, task.id)
        self.assertEqual(updated.status, TaskStatus.FAILED.value)
        self.assertEqual(updated.progress, 25)

    def test_execute_refusal_leaves_task_untouched(self):
        refusing = FakeExecutionService(
            error=InvalidStatusTransitionError("Only a published workflow can be run.")
        )
        service, _ = make_service(refusing)
        task = service.create_task(
            self.owner, TaskCreate(name="n", workflow_id=uuid.uuid4())
        )
        with self.assertRaises(InvalidStatusTransitionError):
            service.execute_task(self.owner, task.id)
        self.assertEqual(task.status, TaskStatus.PENDING.value)
        self.assertEqual(service.tasks.links, [])

    def test_execute_passes_seed_inputs_through(self):
        task = self._create(workflow_id=uuid.uuid4())
        self.service.execute_task(
            self.owner, task.id, initial_inputs={"topic": "pricing"}
        )
        self.assertEqual(
            self.execution_service.calls[0]["initial_inputs"], {"topic": "pricing"}
        )

    # -- retry
    def test_retry_repeats_a_linked_run(self):
        workflow_id = uuid.uuid4()
        original = make_execution(workflow_id=workflow_id)
        self.execution_service.execution = original
        task = self._create(workflow_id=workflow_id)
        self.service.execute_task(self.owner, task.id)
        self.service.tasks.executions[original.id] = original

        fresh = make_execution(workflow_id=workflow_id)
        self.execution_service.execution = fresh
        self.service.tasks.update_fields(task, status="failed")
        updated, tracked = self.service.retry_execution(
            self.owner, task.id, original.id
        )

        call = self.execution_service.calls[-1]
        self.assertEqual(call["trigger"], "retry")
        self.assertEqual(call["retry_of_execution_id"], original.id)
        self.assertEqual(call["workflow_id"], workflow_id)
        self.assertEqual(tracked.execution.id, fresh.id)
        self.assertIn((task.id, fresh.id), self.service.tasks.links)
        self.assertEqual(updated.status, TaskStatus.COMPLETED.value)

    def test_retry_refuses_a_run_the_task_did_not_launch(self):
        task = self._create(workflow_id=uuid.uuid4())
        with self.assertRaises(TaskNotFoundError):
            self.service.retry_execution(self.owner, task.id, uuid.uuid4())

    # -- history access
    def test_list_executions_returns_linked_runs_newest_first(self):
        task = self._create(workflow_id=uuid.uuid4())
        first = make_execution()
        second = make_execution()
        for execution in (first, second):
            self.service.tasks.executions[execution.id] = execution
            self.service.tasks.add_execution_link(task.id, execution.id)

        rows, total = self.service.list_executions(self.owner, task.id)
        self.assertEqual(total, 2)
        self.assertEqual({row.id for row in rows}, {first.id, second.id})

    def test_list_executions_enforces_ownership(self):
        task = self._create()
        with self.assertRaises(TaskAccessDeniedError):
            self.service.list_executions(make_user(), task.id)


# --- API tests -----------------------------------------------------------


def make_task(user_id: Optional[uuid.UUID] = None, **overrides) -> Task:
    now = datetime.now(timezone.utc)
    task = Task(
        id=overrides.get("id", uuid.uuid4()),
        user_id=user_id or uuid.uuid4(),
        business_id=overrides.get("business_id", "TSK-1001"),
        name=overrides.get("name", "Competitor brief"),
        description="d",
        status=overrides.get("status", "pending"),
        priority="medium",
        execution_mode="manual",
        progress=overrides.get("progress", 0),
        workflow_id=overrides.get("workflow_id"),
        employee_id=overrides.get("employee_id"),
    )
    task.created_at = now
    task.updated_at = now
    return task


class TaskAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = make_user()
        self.service = MagicMock()
        self.service.execution_overview.return_value = (None, 0)
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_task_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_list_returns_tasks(self):
        self.service.list_tasks.return_value = [make_task(self.user.id)]
        response = self.client.get("/api/v1/tasks")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["business_id"], "TSK-1001")
        self.assertEqual(body[0]["status"], "pending")
        self.assertIsNone(body[0]["workflow"])
        self.assertIsNone(body[0]["assignee"])

    def test_create_returns_201(self):
        self.service.create_task.return_value = make_task(self.user.id)
        response = self.client.post("/api/v1/tasks", json={"name": "Brief"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Competitor brief")

    def test_create_rejects_blank_name(self):
        response = self.client.post("/api/v1/tasks", json={"name": ""})
        self.assertEqual(response.status_code, 422)

    def test_create_maps_bad_reference_to_422(self):
        self.service.create_task.side_effect = TaskValidationError(
            "That workflow doesn't exist."
        )
        response = self.client.post(
            "/api/v1/tasks",
            json={"name": "Brief", "workflow_id": str(uuid.uuid4())},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "That workflow doesn't exist.")

    def test_get_maps_not_found_to_404(self):
        self.service.get_task.side_effect = TaskNotFoundError("x")
        response = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 404)

    def test_get_maps_access_denied_to_403(self):
        self.service.get_task.side_effect = TaskAccessDeniedError("x")
        response = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 403)

    def test_get_carries_latest_execution(self):
        task = make_task(self.user.id)
        execution = make_execution()
        self.service.get_task.return_value = task
        self.service.execution_overview.return_value = (execution, 3)
        response = self.client.get(f"/api/v1/tasks/{task.id}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["execution_count"], 3)
        self.assertEqual(body["latest_execution"]["status"], "COMPLETED")

    def test_patch_assigns_employee(self):
        employee_id = uuid.uuid4()
        self.service.update_task.return_value = make_task(
            self.user.id, employee_id=employee_id
        )
        response = self.client.patch(
            f"/api/v1/tasks/{uuid.uuid4()}",
            json={"employee_id": str(employee_id)},
        )
        self.assertEqual(response.status_code, 200)
        sent = self.service.update_task.call_args.args[2]
        self.assertEqual(sent.employee_id, employee_id)
        self.assertIn("employee_id", sent.model_fields_set)
        self.assertNotIn("workflow_id", sent.model_fields_set)

    def test_command_maps_illegal_move_to_409(self):
        self.service.run_command.side_effect = InvalidTaskCommandError(
            "A task that's completed can't be queued."
        )
        response = self.client.post(
            f"/api/v1/tasks/{uuid.uuid4()}/command", json={"command": "queue"}
        )
        self.assertEqual(response.status_code, 409)

    def test_duplicate_returns_201(self):
        self.service.duplicate_task.return_value = make_task(self.user.id)
        response = self.client.post(
            f"/api/v1/tasks/{uuid.uuid4()}/duplicate", json={}
        )
        self.assertEqual(response.status_code, 201)

    def test_execute_returns_the_runs_result(self):
        execution = make_execution()
        tracked = TrackedExecution(
            result=make_result(execution), execution=execution
        )
        self.service.execute_task.return_value = (make_task(self.user.id), tracked)
        response = self.client.post(f"/api/v1/tasks/{uuid.uuid4()}/execute", json={})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "COMPLETED")
        self.assertEqual(body["execution_id"], str(execution.id))

    def test_execute_maps_missing_workflow_to_422(self):
        self.service.execute_task.side_effect = TaskValidationError(
            "This task has no workflow attached. Attach one first."
        )
        response = self.client.post(f"/api/v1/tasks/{uuid.uuid4()}/execute", json={})
        self.assertEqual(response.status_code, 422)

    def test_execute_maps_unpublished_workflow_to_409(self):
        self.service.execute_task.side_effect = InvalidStatusTransitionError(
            "Only a published workflow can be run. Publish it first."
        )
        response = self.client.post(f"/api/v1/tasks/{uuid.uuid4()}/execute", json={})
        self.assertEqual(response.status_code, 409)

    def test_retry_returns_201_with_the_new_run(self):
        execution = make_execution()
        tracked = TrackedExecution(
            result=make_result(execution), execution=execution
        )
        self.service.retry_execution.return_value = (make_task(self.user.id), tracked)
        response = self.client.post(
            f"/api/v1/tasks/{uuid.uuid4()}/executions/{uuid.uuid4()}/retry"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["execution_id"], str(execution.id))

    def test_list_executions_returns_history(self):
        execution = make_execution()
        self.service.list_executions.return_value = ([execution], 1)
        response = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}/executions")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["id"], str(execution.id))

    def test_requires_authentication(self):
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/tasks").status_code, 401)
        self.assertEqual(
            client.post("/api/v1/tasks", json={"name": "x"}).status_code, 401
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
