"""Workflow domain tests (Sprint 18.3).

Three layers, none of which touch a database or network:

* ``WorkflowServiceTests`` run the real :class:`WorkflowService` against an
  in-memory fake repository, so ownership, lifecycle rules, graph validation
  and duplication are exercised for real.
* ``WorkflowAPITests`` drive the endpoints through ``TestClient`` with the
  service mocked, covering HTTP concerns — status codes, error mapping, and
  ownership.
* ``WorkflowGraphTests`` / ``WorkflowLifecycleTests`` cover the pure policy
  modules directly.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_workflows
"""

import unittest
import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_workflow_service
from app.main import app
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services.workflow_graph import (
    WorkflowGraphError,
    empty_graph,
    node_count,
    validate_graph,
)
from app.services.workflow_lifecycle import (
    RESTORABLE_STATUSES,
    allowed_transitions,
    can_transition,
)
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowService,
    WorkflowValidationError,
)
from app.utils.constants import WorkflowStatus


# --- Test doubles --------------------------------------------------------


class FakeSession:
    """Minimal unit-of-work stand-in that records commits."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, instance) -> None:  # pragma: no cover - no-op
        return None


class FakeWorkflowRepository:
    """In-memory mirror of :class:`WorkflowRepository`'s public surface."""

    def __init__(self, session) -> None:
        self.session = session
        self.rows: dict[uuid.UUID, Workflow] = {}

    # -- reads
    def get_by_id(self, workflow_id):
        return self.rows.get(workflow_id)

    def list_by_user(self, user_id, *, skip=0, limit=100):
        rows = [w for w in self.rows.values() if w.user_id == user_id]
        return rows[skip : skip + limit]

    def count_by_name(self, user_id, name, *, exclude_id=None):
        return len(
            [
                w
                for w in self.rows.values()
                if w.user_id == user_id and w.name == name and w.id != exclude_id
            ]
        )

    # -- writes
    def create(self, user_id, *, name, description, graph, status):
        workflow = Workflow(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            description=description,
            graph=graph,
            status=status,
        )
        workflow.archived_at = None
        workflow.created_at = datetime.now(timezone.utc)
        workflow.updated_at = datetime.now(timezone.utc)
        self.rows[workflow.id] = workflow
        return workflow

    def update_fields(self, workflow, **fields):
        for key, value in fields.items():
            setattr(workflow, key, value)
        return workflow

    def set_status(self, workflow, status, *, archived_at=None):
        workflow.status = status
        workflow.archived_at = archived_at
        return workflow

    def delete(self, workflow) -> None:
        self.rows.pop(workflow.id, None)


def make_user(user_id: Optional[uuid.UUID] = None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    return user


def make_service():
    session = FakeSession()
    service = WorkflowService(session)
    service.workflows = FakeWorkflowRepository(session)
    return service, session


GRAPH = {
    "nodes": [{"id": "n1", "kind": "task"}, {"id": "n2", "kind": "output"}],
    "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
}


# --- Service -------------------------------------------------------------


class WorkflowServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, self.session = make_service()
        self.owner = make_user()

    def _create(self, name="Nightly report", graph=None):
        return self.service.create_workflow(
            self.owner,
            WorkflowCreate(name=name, description="d", graph=graph or GRAPH),
        )

    # -- create
    def test_create_persists_and_commits(self):
        workflow = self._create()
        self.assertEqual(workflow.name, "Nightly report")
        self.assertEqual(workflow.status, WorkflowStatus.DRAFT.value)
        self.assertEqual(workflow.user_id, self.owner.id)
        self.assertEqual(self.session.commits, 1)

    def test_create_without_graph_starts_blank(self):
        workflow = self.service.create_workflow(
            self.owner, WorkflowCreate(name="Blank")
        )
        self.assertEqual(workflow.graph, empty_graph())

    def test_create_trims_name(self):
        workflow = self.service.create_workflow(
            self.owner, WorkflowCreate(name="  Spaced  ")
        )
        self.assertEqual(workflow.name, "Spaced")

    def test_create_rejects_duplicate_name(self):
        self._create()
        with self.assertRaises(WorkflowValidationError):
            self._create()

    def test_create_rejects_malformed_graph(self):
        with self.assertRaises(WorkflowValidationError):
            self._create(graph={"nodes": "not a list"})

    def test_create_rejects_dangling_edge(self):
        bad = {"nodes": [{"id": "n1"}], "edges": [{"id": "e1", "source": "n1", "target": "ghost"}]}
        with self.assertRaises(WorkflowValidationError):
            self._create(graph=bad)

    def test_same_name_allowed_for_different_owners(self):
        self._create()
        other = make_user()
        # No exception: uniqueness is per owner, not global.
        self.service.create_workflow(other, WorkflowCreate(name="Nightly report"))

    # -- read / ownership
    def test_get_returns_own_workflow(self):
        created = self._create()
        self.assertEqual(self.service.get_workflow(self.owner, created.id).id, created.id)

    def test_get_missing_raises_not_found(self):
        with self.assertRaises(WorkflowNotFoundError):
            self.service.get_workflow(self.owner, uuid.uuid4())

    def test_get_other_users_workflow_raises_access_denied(self):
        created = self._create()
        with self.assertRaises(WorkflowAccessDeniedError):
            self.service.get_workflow(make_user(), created.id)

    def test_list_only_returns_own_workflows(self):
        self._create()
        other = make_user()
        self.service.create_workflow(other, WorkflowCreate(name="Theirs"))
        self.assertEqual(len(self.service.list_workflows(self.owner)), 1)
        self.assertEqual(len(self.service.list_workflows(other)), 1)

    # -- update
    def test_update_changes_only_supplied_fields(self):
        created = self._create()
        updated = self.service.update_workflow(
            self.owner, created.id, WorkflowUpdate(name="Renamed")
        )
        self.assertEqual(updated.name, "Renamed")
        self.assertEqual(updated.description, "d")

    def test_update_persists_graph(self):
        created = self._create()
        new_graph = {"nodes": [{"id": "only"}], "edges": []}
        updated = self.service.update_workflow(
            self.owner, created.id, WorkflowUpdate(graph=new_graph)
        )
        self.assertEqual(updated.graph, new_graph)

    def test_update_rejects_malformed_graph(self):
        created = self._create()
        with self.assertRaises(WorkflowValidationError):
            self.service.update_workflow(
                self.owner, created.id, WorkflowUpdate(graph={"nodes": [{}]})
            )

    def test_update_rejects_duplicate_name(self):
        self._create(name="First")
        second = self._create(name="Second")
        with self.assertRaises(WorkflowValidationError):
            self.service.update_workflow(
                self.owner, second.id, WorkflowUpdate(name="First")
            )

    def test_update_can_publish(self):
        created = self._create()
        updated = self.service.update_workflow(
            self.owner, created.id, WorkflowUpdate(status=WorkflowStatus.PUBLISHED)
        )
        self.assertEqual(updated.status, WorkflowStatus.PUBLISHED.value)

    def test_update_cannot_archive_via_status(self):
        created = self._create()
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.update_workflow(
                self.owner, created.id, WorkflowUpdate(status=WorkflowStatus.ARCHIVED)
            )

    def test_archived_workflow_cannot_be_edited(self):
        created = self._create()
        self.service.archive_workflow(self.owner, created.id)
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.update_workflow(
                self.owner, created.id, WorkflowUpdate(name="Nope")
            )

    def test_update_other_users_workflow_denied(self):
        created = self._create()
        with self.assertRaises(WorkflowAccessDeniedError):
            self.service.update_workflow(
                make_user(), created.id, WorkflowUpdate(name="Hijack")
            )

    # -- archive / restore
    def test_archive_sets_status_and_timestamp(self):
        created = self._create()
        archived = self.service.archive_workflow(self.owner, created.id)
        self.assertEqual(archived.status, WorkflowStatus.ARCHIVED.value)
        self.assertIsNotNone(archived.archived_at)

    def test_archive_twice_conflicts(self):
        created = self._create()
        self.service.archive_workflow(self.owner, created.id)
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.archive_workflow(self.owner, created.id)

    def test_restore_returns_to_draft_and_clears_timestamp(self):
        created = self._create()
        self.service.archive_workflow(self.owner, created.id)
        restored = self.service.restore_workflow(self.owner, created.id)
        self.assertEqual(restored.status, WorkflowStatus.DRAFT.value)
        self.assertIsNone(restored.archived_at)

    def test_restore_unarchived_conflicts(self):
        created = self._create()
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.restore_workflow(self.owner, created.id)

    def test_restore_directly_to_published_rejected(self):
        created = self._create()
        self.service.archive_workflow(self.owner, created.id)
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.restore_workflow(
                self.owner, created.id, WorkflowStatus.PUBLISHED
            )

    def test_archive_other_users_workflow_denied(self):
        created = self._create()
        with self.assertRaises(WorkflowAccessDeniedError):
            self.service.archive_workflow(make_user(), created.id)

    # -- duplicate
    def test_duplicate_copies_graph_as_new_draft(self):
        created = self._create()
        self.service.update_workflow(
            self.owner, created.id, WorkflowUpdate(status=WorkflowStatus.PUBLISHED)
        )
        clone = self.service.duplicate_workflow(self.owner, created.id)
        self.assertNotEqual(clone.id, created.id)
        self.assertEqual(clone.graph, created.graph)
        # A copy is never born published.
        self.assertEqual(clone.status, WorkflowStatus.DRAFT.value)

    def test_duplicate_derives_free_name(self):
        created = self._create(name="Report")
        first = self.service.duplicate_workflow(self.owner, created.id)
        second = self.service.duplicate_workflow(self.owner, created.id)
        self.assertEqual(first.name, "Report (copy)")
        self.assertEqual(second.name, "Report (copy) 2")

    def test_duplicate_accepts_explicit_name(self):
        created = self._create()
        clone = self.service.duplicate_workflow(self.owner, created.id, "Chosen")
        self.assertEqual(clone.name, "Chosen")

    def test_duplicate_does_not_share_graph_object(self):
        created = self._create()
        clone = self.service.duplicate_workflow(self.owner, created.id)
        clone.graph["nodes"].append({"id": "n3"})
        # Mutating the clone must not reach back into the source.
        self.assertEqual(len(created.graph["nodes"]), 2)

    def test_duplicate_other_users_workflow_denied(self):
        created = self._create()
        with self.assertRaises(WorkflowAccessDeniedError):
            self.service.duplicate_workflow(make_user(), created.id)

    # -- delete
    def test_delete_removes_workflow(self):
        created = self._create()
        self.service.delete_workflow(self.owner, created.id)
        with self.assertRaises(WorkflowNotFoundError):
            self.service.get_workflow(self.owner, created.id)

    def test_delete_other_users_workflow_denied(self):
        created = self._create()
        with self.assertRaises(WorkflowAccessDeniedError):
            self.service.delete_workflow(make_user(), created.id)
        # And it is still there.
        self.assertIsNotNone(self.service.get_workflow(self.owner, created.id))


# --- Graph policy --------------------------------------------------------


class WorkflowGraphTests(unittest.TestCase):
    def test_valid_graph_returned_unchanged(self):
        self.assertEqual(validate_graph(GRAPH), GRAPH)

    def test_empty_graph_is_valid(self):
        self.assertEqual(validate_graph(empty_graph()), empty_graph())

    def test_missing_keys_default_to_empty(self):
        self.assertEqual(validate_graph({}), {})

    def test_graph_must_be_object(self):
        for bad in ([], "graph", 7, None):
            with self.assertRaises(WorkflowGraphError):
                validate_graph(bad)

    def test_nodes_must_be_list(self):
        with self.assertRaises(WorkflowGraphError):
            validate_graph({"nodes": {}})

    def test_node_needs_non_empty_id(self):
        for bad in ({}, {"id": ""}, {"id": "   "}, {"id": 5}):
            with self.assertRaises(WorkflowGraphError):
                validate_graph({"nodes": [bad], "edges": []})

    def test_duplicate_node_id_rejected(self):
        with self.assertRaises(WorkflowGraphError):
            validate_graph({"nodes": [{"id": "a"}, {"id": "a"}], "edges": []})

    def test_duplicate_edge_id_rejected(self):
        graph = {
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [
                {"id": "e", "source": "a", "target": "b"},
                {"id": "e", "source": "b", "target": "a"},
            ],
        }
        with self.assertRaises(WorkflowGraphError):
            validate_graph(graph)

    def test_edge_endpoints_must_exist(self):
        graph = {"nodes": [{"id": "a"}], "edges": [{"id": "e", "source": "a", "target": "b"}]}
        with self.assertRaises(WorkflowGraphError):
            validate_graph(graph)

    def test_unknown_node_keys_are_preserved(self):
        graph = {
            "nodes": [{"id": "a", "kind": "task", "position": {"x": 1, "y": 2}}],
            "edges": [],
        }
        # Node kinds are the frontend's vocabulary; the backend stores them.
        self.assertEqual(validate_graph(graph)["nodes"][0]["position"], {"x": 1, "y": 2})

    def test_node_count(self):
        self.assertEqual(node_count(GRAPH), 2)
        self.assertEqual(node_count(empty_graph()), 0)
        self.assertEqual(node_count({}), 0)


# --- Lifecycle policy ----------------------------------------------------


class WorkflowLifecycleTests(unittest.TestCase):
    def test_draft_can_publish_and_archive(self):
        self.assertTrue(can_transition(WorkflowStatus.DRAFT, WorkflowStatus.PUBLISHED))
        self.assertTrue(can_transition(WorkflowStatus.DRAFT, WorkflowStatus.ARCHIVED))

    def test_published_can_return_to_draft(self):
        self.assertTrue(can_transition(WorkflowStatus.PUBLISHED, WorkflowStatus.DRAFT))

    def test_archived_is_terminal(self):
        self.assertEqual(allowed_transitions(WorkflowStatus.ARCHIVED), frozenset())
        self.assertFalse(
            can_transition(WorkflowStatus.ARCHIVED, WorkflowStatus.PUBLISHED)
        )

    def test_staying_put_is_allowed(self):
        for stat in WorkflowStatus:
            self.assertTrue(can_transition(stat, stat))

    def test_restorable_statuses(self):
        self.assertEqual(RESTORABLE_STATUSES, frozenset({WorkflowStatus.DRAFT}))


# --- API -----------------------------------------------------------------


def make_workflow(**overrides):
    workflow = Workflow(
        id=overrides.get("id", uuid.uuid4()),
        user_id=overrides.get("user_id", uuid.uuid4()),
        name=overrides.get("name", "Nightly report"),
        description=overrides.get("description", "d"),
        graph=overrides.get("graph", GRAPH),
        status=overrides.get("status", WorkflowStatus.DRAFT.value),
    )
    workflow.archived_at = overrides.get("archived_at")
    workflow.created_at = datetime.now(timezone.utc)
    workflow.updated_at = datetime.now(timezone.utc)
    return workflow


class WorkflowAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = make_user()
        self.service = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_workflow_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_list_returns_summaries_without_graph(self):
        self.service.list_workflows.return_value = [make_workflow()]
        response = self.client.get("/api/v1/workflows")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["node_count"], 2)
        self.assertNotIn("graph", body[0])

    def test_create_returns_201_with_graph(self):
        self.service.create_workflow.return_value = make_workflow()
        response = self.client.post("/api/v1/workflows", json={"name": "Nightly report"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["graph"], GRAPH)

    def test_create_rejects_blank_name(self):
        response = self.client.post("/api/v1/workflows", json={"name": ""})
        self.assertEqual(response.status_code, 422)

    def test_create_validation_error_maps_to_422(self):
        self.service.create_workflow.side_effect = WorkflowValidationError("bad graph")
        response = self.client.post("/api/v1/workflows", json={"name": "x"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "bad graph")

    def test_get_missing_maps_to_404(self):
        self.service.get_workflow.side_effect = WorkflowNotFoundError("nope")
        response = self.client.get(f"/api/v1/workflows/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 404)

    def test_get_other_users_maps_to_403(self):
        self.service.get_workflow.side_effect = WorkflowAccessDeniedError("nope")
        response = self.client.get(f"/api/v1/workflows/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 403)

    def test_get_rejects_non_uuid(self):
        response = self.client.get("/api/v1/workflows/not-a-uuid")
        self.assertEqual(response.status_code, 422)

    def test_patch_returns_updated(self):
        self.service.update_workflow.return_value = make_workflow(name="Renamed")
        response = self.client.patch(
            f"/api/v1/workflows/{uuid.uuid4()}", json={"name": "Renamed"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Renamed")

    def test_patch_invalid_transition_maps_to_409(self):
        self.service.update_workflow.side_effect = InvalidStatusTransitionError(
            "An archived workflow cannot be edited. Restore it first."
        )
        response = self.client.patch(
            f"/api/v1/workflows/{uuid.uuid4()}", json={"name": "x"}
        )
        self.assertEqual(response.status_code, 409)

    def test_delete_returns_204(self):
        self.service.delete_workflow.return_value = None
        response = self.client.delete(f"/api/v1/workflows/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 204)

    def test_archive_returns_workflow(self):
        self.service.archive_workflow.return_value = make_workflow(
            status=WorkflowStatus.ARCHIVED.value, archived_at=datetime.now(timezone.utc)
        )
        response = self.client.post(f"/api/v1/workflows/{uuid.uuid4()}/archive")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "archived")

    def test_archive_conflict_maps_to_409(self):
        self.service.archive_workflow.side_effect = InvalidStatusTransitionError(
            "That workflow is already archived."
        )
        response = self.client.post(f"/api/v1/workflows/{uuid.uuid4()}/archive")
        self.assertEqual(response.status_code, 409)

    def test_restore_defaults_to_draft(self):
        self.service.restore_workflow.return_value = make_workflow()
        response = self.client.post(
            f"/api/v1/workflows/{uuid.uuid4()}/restore", json={}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.service.restore_workflow.call_args[0][2], WorkflowStatus.DRAFT
        )

    def test_restore_rejects_unknown_status(self):
        response = self.client.post(
            f"/api/v1/workflows/{uuid.uuid4()}/restore", json={"status": "nonsense"}
        )
        self.assertEqual(response.status_code, 422)

    def test_duplicate_returns_201(self):
        self.service.duplicate_workflow.return_value = make_workflow(
            name="Nightly report (copy)"
        )
        response = self.client.post(
            f"/api/v1/workflows/{uuid.uuid4()}/duplicate", json={}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Nightly report (copy)")

    def test_endpoints_require_authentication(self):
        # Drop the auth override so the real bearer dependency runs. A missing
        # Authorization header is rejected by the scheme with 401, matching
        # every other protected route.
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/workflows").status_code, 401)
        self.assertEqual(
            client.post("/api/v1/workflows", json={"name": "x"}).status_code, 401
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
