"""Memory integration tests (linking memories to tasks/workflows + user-wide read).

Two layers, neither touching a database or network:

* ``MemoryLinkServiceTests`` run the real :class:`MemoryLinkService` with its
  reused ownership seams (Employee/Task/Workflow) mocked and an in-memory fake
  link repository, so attaching, detaching, idempotency, reference validation,
  permission propagation and the user-wide search are exercised for real.
* ``MemoryLinkAPITests`` drive the endpoints through ``TestClient`` with the
  service mocked, covering HTTP concerns — status codes, error mapping, DTO
  shapes, ownership and auth.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_memory_links
"""

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_memory_link_service
from app.main import app
from app.models.memory import Memory
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
)
from app.services.memory_link_service import (
    MemoryLinkNotFoundError,
    MemoryLinkService,
    MemoryReferenceError,
)
from app.services.task_service import TaskAccessDeniedError, TaskNotFoundError
from app.services.workflow_service import (
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
)


# --- Test doubles --------------------------------------------------------


class FakeSession:
    """Minimal unit-of-work stand-in that records commits."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, instance) -> None:  # pragma: no cover - no-op
        return None


class FakeLink:
    def __init__(self, parent_id: uuid.UUID, memory_id: uuid.UUID) -> None:
        self.parent_id = parent_id
        self.memory_id = memory_id


class FakeMemoryLinkRepository:
    """In-memory mirror of :class:`MemoryLinkRepository`'s public surface."""

    def __init__(self) -> None:
        self.task_links: list[FakeLink] = []
        self.workflow_links: list[FakeLink] = []
        # (Memory, employee_name) rows for the user-wide read.
        self.user_rows: list[tuple[Memory, str]] = []

    # -- task links
    def get_task_link(self, task_id, memory_id):
        return next(
            (
                l
                for l in self.task_links
                if l.parent_id == task_id and l.memory_id == memory_id
            ),
            None,
        )

    def add_task_link(self, task_id, memory_id):
        link = FakeLink(task_id, memory_id)
        self.task_links.append(link)
        return link

    def delete_task_link(self, link):
        self.task_links.remove(link)

    def list_task_memories(self, task_id):
        ids = [l.memory_id for l in self.task_links if l.parent_id == task_id]
        return [(m, n) for (m, n) in self.user_rows if m.id in ids]

    # -- workflow links
    def get_workflow_link(self, workflow_id, memory_id):
        return next(
            (
                l
                for l in self.workflow_links
                if l.parent_id == workflow_id and l.memory_id == memory_id
            ),
            None,
        )

    def add_workflow_link(self, workflow_id, memory_id):
        link = FakeLink(workflow_id, memory_id)
        self.workflow_links.append(link)
        return link

    def delete_workflow_link(self, link):
        self.workflow_links.remove(link)

    def list_workflow_memories(self, workflow_id):
        ids = [
            l.memory_id for l in self.workflow_links if l.parent_id == workflow_id
        ]
        return [(m, n) for (m, n) in self.user_rows if m.id in ids]

    # -- user-wide reads
    def search_user_memories(
        self,
        user_id,
        *,
        keyword=None,
        memory_type=None,
        min_importance=None,
        limit=50,
        offset=0,
    ):
        rows = self.user_rows
        if keyword:
            rows = [r for r in rows if keyword.lower() in r[0].content.lower()]
        if memory_type is not None:
            rows = [r for r in rows if r[0].memory_type == memory_type]
        if min_importance is not None:
            rows = [r for r in rows if r[0].importance_score >= min_importance]
        return rows[offset : offset + limit]

    def count_user_memories(self, user_id):
        return len(self.user_rows)


class FakeMemoryRepository:
    """Stands in for the reused Sprint 2 ``MemoryRepository`` (read only)."""

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Memory] = {}

    def get_memory(self, memory_id):
        return self.rows.get(memory_id)


# --- Helpers -------------------------------------------------------------


def make_user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4())


def make_memory(
    employee_id: Optional[uuid.UUID] = None,
    *,
    content: str = "Prefers async standups.",
    memory_type: str = "permanent",
    importance: float = 0.5,
) -> Memory:
    memory = Memory(
        id=uuid.uuid4(),
        employee_id=employee_id or uuid.uuid4(),
        memory_type=memory_type,
        content=content,
        importance_score=importance,
    )
    memory.created_at = datetime.now(timezone.utc)
    return memory


def build_service() -> MemoryLinkService:
    """A real service with its reused seams and link repo replaced by fakes."""
    service = MemoryLinkService(FakeSession())
    service.links = FakeMemoryLinkRepository()
    service.memories = FakeMemoryRepository()
    service.employees = MagicMock()
    service.tasks = MagicMock()
    service.workflows = MagicMock()
    return service


# --- Service tests -------------------------------------------------------


class MemoryLinkServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = make_user()
        self.service = build_service()
        self.employee_id = uuid.uuid4()
        self.memory = make_memory(self.employee_id)
        self.service.memories.rows[self.memory.id] = self.memory
        # By default the owner owns everything they reference.
        self.service.employees.get_employee.return_value = SimpleNamespace(
            id=self.employee_id, name="Atlas"
        )
        self.service.tasks.get_task.return_value = SimpleNamespace(id=uuid.uuid4())
        self.service.workflows.get_workflow.return_value = SimpleNamespace(
            id=uuid.uuid4()
        )

    # -- attach (task)
    def test_attach_memory_to_task_links_and_returns_owner_name(self) -> None:
        task_id = uuid.uuid4()
        memory, name = self.service.attach_memory_to_task(
            self.owner, task_id, self.memory.id
        )
        self.assertEqual(memory.id, self.memory.id)
        self.assertEqual(name, "Atlas")
        self.assertIsNotNone(self.service.links.get_task_link(task_id, self.memory.id))
        self.assertEqual(self.service.session.commits, 1)
        self.service.tasks.get_task.assert_called_once()

    def test_attach_is_idempotent(self) -> None:
        task_id = uuid.uuid4()
        self.service.attach_memory_to_task(self.owner, task_id, self.memory.id)
        self.service.attach_memory_to_task(self.owner, task_id, self.memory.id)
        # One link, one commit — a repeat attach is a no-op, not a duplicate.
        self.assertEqual(len(self.service.links.task_links), 1)
        self.assertEqual(self.service.session.commits, 1)

    def test_attach_missing_memory_raises_reference_error(self) -> None:
        with self.assertRaises(MemoryReferenceError):
            self.service.attach_memory_to_task(
                self.owner, uuid.uuid4(), uuid.uuid4()
            )

    def test_attach_foreign_memory_raises_reference_error(self) -> None:
        # The memory exists but its employee isn't the owner's.
        self.service.employees.get_employee.side_effect = EmployeeAccessDeniedError(
            "nope"
        )
        with self.assertRaises(MemoryReferenceError):
            self.service.attach_memory_to_task(
                self.owner, uuid.uuid4(), self.memory.id
            )
        # Nothing was linked or committed.
        self.assertEqual(len(self.service.links.task_links), 0)
        self.assertEqual(self.service.session.commits, 0)

    def test_attach_foreign_task_propagates_access_denied(self) -> None:
        self.service.tasks.get_task.side_effect = TaskAccessDeniedError("nope")
        with self.assertRaises(TaskAccessDeniedError):
            self.service.attach_memory_to_task(
                self.owner, uuid.uuid4(), self.memory.id
            )

    def test_attach_missing_task_propagates_not_found(self) -> None:
        self.service.tasks.get_task.side_effect = TaskNotFoundError("nope")
        with self.assertRaises(TaskNotFoundError):
            self.service.attach_memory_to_task(
                self.owner, uuid.uuid4(), self.memory.id
            )

    # -- detach (task)
    def test_detach_removes_link(self) -> None:
        task_id = uuid.uuid4()
        self.service.attach_memory_to_task(self.owner, task_id, self.memory.id)
        self.service.detach_memory_from_task(self.owner, task_id, self.memory.id)
        self.assertIsNone(self.service.links.get_task_link(task_id, self.memory.id))
        # attach commit + detach commit
        self.assertEqual(self.service.session.commits, 2)

    def test_detach_unlinked_raises_not_found(self) -> None:
        with self.assertRaises(MemoryLinkNotFoundError):
            self.service.detach_memory_from_task(
                self.owner, uuid.uuid4(), self.memory.id
            )

    # -- list (task)
    def test_list_task_memories_checks_ownership(self) -> None:
        task_id = uuid.uuid4()
        self.service.links.user_rows.append((self.memory, "Atlas"))
        self.service.attach_memory_to_task(self.owner, task_id, self.memory.id)
        rows = self.service.list_task_memories(self.owner, task_id)
        self.assertEqual([m.id for m, _ in rows], [self.memory.id])

    def test_list_task_memories_missing_task_propagates(self) -> None:
        self.service.tasks.get_task.side_effect = TaskNotFoundError("nope")
        with self.assertRaises(TaskNotFoundError):
            self.service.list_task_memories(self.owner, uuid.uuid4())

    # -- workflow side (mirror)
    def test_attach_memory_to_workflow_links(self) -> None:
        workflow_id = uuid.uuid4()
        memory, name = self.service.attach_memory_to_workflow(
            self.owner, workflow_id, self.memory.id
        )
        self.assertEqual(memory.id, self.memory.id)
        self.assertIsNotNone(
            self.service.links.get_workflow_link(workflow_id, self.memory.id)
        )
        self.assertEqual(self.service.session.commits, 1)

    def test_attach_workflow_foreign_propagates_access_denied(self) -> None:
        self.service.workflows.get_workflow.side_effect = WorkflowAccessDeniedError(
            "nope"
        )
        with self.assertRaises(WorkflowAccessDeniedError):
            self.service.attach_memory_to_workflow(
                self.owner, uuid.uuid4(), self.memory.id
            )

    def test_detach_workflow_unlinked_raises_not_found(self) -> None:
        with self.assertRaises(MemoryLinkNotFoundError):
            self.service.detach_memory_from_workflow(
                self.owner, uuid.uuid4(), self.memory.id
            )

    # -- ownership resolution
    def test_owned_memory_missing_employee_raises_reference_error(self) -> None:
        self.service.employees.get_employee.side_effect = EmployeeNotFoundError(
            "gone"
        )
        with self.assertRaises(MemoryReferenceError):
            self.service.attach_memory_to_workflow(
                self.owner, uuid.uuid4(), self.memory.id
            )

    # -- user-wide search
    def test_search_returns_rows_and_total(self) -> None:
        m1 = make_memory(self.employee_id, content="Ship the invoice report")
        m2 = make_memory(self.employee_id, content="Async standups preferred")
        self.service.links.user_rows = [(m1, "Atlas"), (m2, "Atlas")]

        rows, total = self.service.search_memories(self.owner, keyword="invoice")
        self.assertEqual([m.id for m, _ in rows], [m1.id])
        # total is the whole count, independent of the keyword filter.
        self.assertEqual(total, 2)

    def test_search_caps_limit(self) -> None:
        captured = {}

        def fake_search(user_id, **kwargs):
            captured.update(kwargs)
            return []

        self.service.links.search_user_memories = fake_search
        self.service.links.count_user_memories = lambda user_id: 0
        self.service.search_memories(self.owner, limit=10_000)
        self.assertEqual(captured["limit"], MemoryLinkService.MAX_LIMIT)


# --- API tests -----------------------------------------------------------


class MemoryLinkAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.user = make_user()
        self.service = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_memory_link_service] = lambda: self.service

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _memory_row(self):
        memory = make_memory(content="Prefers async standups.")
        return memory, "Atlas"

    def test_list_user_memories_shape(self) -> None:
        memory, name = self._memory_row()
        self.service.search_memories.return_value = ([(memory, name)], 1)

        resp = self.client.get("/api/v1/memories?q=async")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["employee_name"], "Atlas")
        self.assertEqual(body["items"][0]["content"], "Prefers async standups.")

    def test_link_task_memory_returns_201(self) -> None:
        memory, name = self._memory_row()
        self.service.attach_memory_to_task.return_value = (memory, name)

        resp = self.client.post(
            f"/api/v1/tasks/{uuid.uuid4()}/memories",
            json={"memory_id": str(memory.id)},
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["id"], str(memory.id))
        self.assertEqual(resp.json()["employee_name"], "Atlas")

    def test_link_task_memory_missing_memory_is_404(self) -> None:
        self.service.attach_memory_to_task.side_effect = MemoryReferenceError("x")
        resp = self.client.post(
            f"/api/v1/tasks/{uuid.uuid4()}/memories",
            json={"memory_id": str(uuid.uuid4())},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "Memory not found.")

    def test_link_task_memory_foreign_task_is_403(self) -> None:
        self.service.attach_memory_to_task.side_effect = TaskAccessDeniedError("x")
        resp = self.client.post(
            f"/api/v1/tasks/{uuid.uuid4()}/memories",
            json={"memory_id": str(uuid.uuid4())},
        )
        self.assertEqual(resp.status_code, 403)

    def test_list_task_memories_missing_task_is_404(self) -> None:
        self.service.list_task_memories.side_effect = TaskNotFoundError("x")
        resp = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}/memories")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "Task not found.")

    def test_unlink_task_memory_returns_204(self) -> None:
        self.service.detach_memory_from_task.return_value = None
        resp = self.client.delete(
            f"/api/v1/tasks/{uuid.uuid4()}/memories/{uuid.uuid4()}"
        )
        self.assertEqual(resp.status_code, 204)

    def test_unlink_task_memory_not_linked_is_404(self) -> None:
        self.service.detach_memory_from_task.side_effect = MemoryLinkNotFoundError(
            "x"
        )
        resp = self.client.delete(
            f"/api/v1/tasks/{uuid.uuid4()}/memories/{uuid.uuid4()}"
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "That memory isn't linked here.")

    def test_link_workflow_memory_returns_201(self) -> None:
        memory, name = self._memory_row()
        self.service.attach_memory_to_workflow.return_value = (memory, name)
        resp = self.client.post(
            f"/api/v1/workflows/{uuid.uuid4()}/memories",
            json={"memory_id": str(memory.id)},
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["id"], str(memory.id))

    def test_link_workflow_memory_foreign_is_403(self) -> None:
        self.service.attach_memory_to_workflow.side_effect = (
            WorkflowAccessDeniedError("x")
        )
        resp = self.client.post(
            f"/api/v1/workflows/{uuid.uuid4()}/memories",
            json={"memory_id": str(uuid.uuid4())},
        )
        self.assertEqual(resp.status_code, 403)

    def test_list_workflow_memories_missing_is_404(self) -> None:
        self.service.list_workflow_memories.side_effect = WorkflowNotFoundError("x")
        resp = self.client.get(f"/api/v1/workflows/{uuid.uuid4()}/memories")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "Workflow not found.")

    def test_unlink_workflow_memory_returns_204(self) -> None:
        self.service.detach_memory_from_workflow.return_value = None
        resp = self.client.delete(
            f"/api/v1/workflows/{uuid.uuid4()}/memories/{uuid.uuid4()}"
        )
        self.assertEqual(resp.status_code, 204)

    def test_unauthenticated_is_401(self) -> None:
        # Drop the auth override so the bearer scheme rejects the request.
        app.dependency_overrides.pop(get_current_user, None)
        resp = self.client.get("/api/v1/memories")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
