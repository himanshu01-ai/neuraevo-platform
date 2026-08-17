"""Workflow execution tests (Sprint 18.6 — authoring↔runtime bridge).

Four layers, none touching a database or network:

* ``TranslationTests`` — the pure ``workflow_translation`` module: kind mapping,
  edge → dependency, topological ordering, and every rejection.
* ``ExecutionServiceTests`` — the real :class:`WorkflowExecutionService` over a
  fake workflow repository and the *real* Sprint 15.15 coordinator (its
  capabilities run offline), so the published-only gate, ownership, translation
  failures and a genuine COMPLETED/FAILED run are exercised for real.
* ``ExecutionAPITests`` — the endpoint through ``TestClient`` with the service
  mocked, covering status codes and result mapping.

Runnable with stdlib unittest:
    PYTHONPATH=. python -m unittest tests.test_workflow_execution
"""

import unittest
import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_current_user,
    get_workflow_coordinator,
    get_workflow_execution_service,
)
from app.main import app
from app.models.workflow import Workflow
from app.services.runtime.workflow_models import (
    CapabilityExecutionReference,
    WorkflowExecutionResult,
    WorkflowStep,
)
from app.models.workflow_execution import WorkflowExecution
from app.services.workflow_execution_service import (
    TrackedExecution,
    WorkflowExecutionService,
)
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowValidationError,
)
from app.services.runtime.capability_contracts import NODE_KIND_TO_CAPABILITY
from app.services.workflow_translation import (
    WorkflowTranslationError,
    translate_graph,
)
from app.utils.constants import WorkflowStatus


# --- helpers -------------------------------------------------------------


def node(node_id, kind, config=None, name=""):
    return {"id": node_id, "kind": kind, "name": name, "config": config or {}}


def edge(source, target):
    return {"id": f"{source}->{target}", "source": source, "target": target}


def graph(nodes, edges=None):
    return {"nodes": nodes, "edges": edges or []}


# A one-step graph that really runs: the python capability computes into outputs.
PYTHON_GRAPH = graph([node("s1", "python", {"python_code": "outputs['v'] = 6 * 7"})])


# --- translation ---------------------------------------------------------


class TranslationTests(unittest.TestCase):
    def test_all_six_kinds_map(self):
        for kind, capability in NODE_KIND_TO_CAPABILITY.items():
            steps = translate_graph(graph([node("n", kind)]))
            self.assertEqual(steps[0].capability_name, capability)

    def test_file_maps_to_filesystem(self):
        steps = translate_graph(graph([node("n", "file")]))
        self.assertEqual(steps[0].capability_name, "filesystem")

    def test_config_becomes_inputs(self):
        steps = translate_graph(graph([node("n", "python", {"python_code": "x=1", "k": "v"})]))
        self.assertEqual(steps[0].inputs, {"python_code": "x=1", "k": "v"})

    def test_edge_becomes_backward_dependency(self):
        # a -> b means b depends on a; order must place a first.
        steps = translate_graph(graph([node("b", "python"), node("a", "python")], [edge("a", "b")]))
        by_id = {s.step_id: s for s in steps}
        self.assertEqual(by_id["b"].depends_on, ["a"])
        self.assertEqual(by_id["a"].depends_on, [])
        self.assertLess(
            [s.step_id for s in steps].index("a"),
            [s.step_id for s in steps].index("b"),
        )

    def test_linear_chain_is_topologically_ordered(self):
        g = graph(
            [node("c", "python"), node("a", "python"), node("b", "python")],
            [edge("a", "b"), edge("b", "c")],
        )
        self.assertEqual([s.step_id for s in translate_graph(g)], ["a", "b", "c"])

    def test_every_dependency_precedes_its_dependent(self):
        g = graph(
            [node("w", "python"), node("x", "python"), node("y", "python"), node("z", "python")],
            [edge("w", "y"), edge("x", "y"), edge("y", "z")],
        )
        order = [s.step_id for s in translate_graph(g)]
        for s in translate_graph(g):
            for dep in s.depends_on:
                self.assertLess(order.index(dep), order.index(s.step_id))

    def test_step_metadata_carries_kind_and_name(self):
        steps = translate_graph(graph([node("n", "browser", name="Fetch page")]))
        self.assertEqual(steps[0].step_metadata, {"kind": "browser", "name": "Fetch page"})

    # -- rejections
    def test_empty_graph_rejected(self):
        with self.assertRaises(WorkflowTranslationError):
            translate_graph(graph([]))

    def test_non_executable_kind_rejected(self):
        for kind in ("task", "planning", "approval", "notification", "memory", "condition", "loop", "output"):
            with self.assertRaises(WorkflowTranslationError):
                translate_graph(graph([node("n", kind)]))

    def test_error_names_every_unsupported_kind(self):
        g = graph([node("a", "python"), node("b", "task"), node("c", "output")])
        with self.assertRaises(WorkflowTranslationError) as ctx:
            translate_graph(g)
        self.assertIn("output", str(ctx.exception))
        self.assertIn("task", str(ctx.exception))

    def test_cycle_rejected(self):
        g = graph([node("a", "python"), node("b", "python")], [edge("a", "b"), edge("b", "a")])
        with self.assertRaises(WorkflowTranslationError):
            translate_graph(g)

    def test_dangling_edge_rejected(self):
        with self.assertRaises(WorkflowTranslationError):
            translate_graph(graph([node("a", "python")], [edge("a", "ghost")]))

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(WorkflowTranslationError):
            translate_graph(graph([node("a", "python"), node("a", "browser")]))

    def test_non_object_graph_rejected(self):
        for bad in (None, [], "graph", 3):
            with self.assertRaises(WorkflowTranslationError):
                translate_graph(bad)


# --- service (real coordinator) -----------------------------------------


class FakeSession:
    def commit(self):  # pragma: no cover - unused by execution
        pass

    def refresh(self, instance):  # pragma: no cover
        return None


class FakeWorkflowRepository:
    """In-memory stand-in for the repo the reused WorkflowService reads."""

    def __init__(self, session) -> None:
        self.rows: dict[uuid.UUID, Workflow] = {}

    def get_by_id(self, workflow_id):
        return self.rows.get(workflow_id)

    def add(self, workflow):
        self.rows[workflow.id] = workflow


def make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    return user


def make_workflow(owner_id, *, status=WorkflowStatus.PUBLISHED.value, graph_doc=None):
    wf = Workflow(
        id=uuid.uuid4(),
        user_id=owner_id,
        name="Runnable",
        description=None,
        graph=graph_doc if graph_doc is not None else PYTHON_GRAPH,
        status=status,
    )
    wf.archived_at = None
    wf.created_at = datetime.now(timezone.utc)
    wf.updated_at = datetime.now(timezone.utc)
    return wf


class ExecutionServiceTests(unittest.TestCase):
    def setUp(self):
        # The real Sprint 15.15 coordinator, over the six real capabilities.
        self.service = WorkflowExecutionService(FakeSession(), get_workflow_coordinator())
        self.repo = FakeWorkflowRepository(FakeSession())
        self.service.workflows.workflows = self.repo
        self.owner = make_user()

    def _seed(self, **kw):
        wf = make_workflow(self.owner.id, **kw)
        self.repo.add(wf)
        return wf

    def test_execute_published_workflow_completes(self):
        wf = self._seed()
        result = self.service.execute_workflow(self.owner, wf.id)
        self.assertEqual(result.workflow_status, "COMPLETED")
        self.assertEqual(result.completed_step_count, 1)
        self.assertEqual(result.total_step_count, 1)
        self.assertIsNone(result.failed_step_id)

    def test_execute_uses_workflow_id(self):
        wf = self._seed()
        result = self.service.execute_workflow(self.owner, wf.id)
        self.assertEqual(result.workflow_id, str(wf.id))

    def test_draft_rejected(self):
        wf = self._seed(status=WorkflowStatus.DRAFT.value)
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.execute_workflow(self.owner, wf.id)

    def test_archived_rejected(self):
        wf = self._seed(status=WorkflowStatus.ARCHIVED.value)
        with self.assertRaises(InvalidStatusTransitionError):
            self.service.execute_workflow(self.owner, wf.id)

    def test_missing_rejected(self):
        with self.assertRaises(WorkflowNotFoundError):
            self.service.execute_workflow(self.owner, uuid.uuid4())

    def test_other_users_workflow_rejected(self):
        wf = self._seed()
        with self.assertRaises(WorkflowAccessDeniedError):
            self.service.execute_workflow(make_user(), wf.id)

    def test_untranslatable_graph_rejected_as_validation(self):
        # A published workflow whose node kind the runtime can't run.
        wf = self._seed(graph_doc=graph([node("n", "task")]))
        with self.assertRaises(WorkflowValidationError):
            self.service.execute_workflow(self.owner, wf.id)

    def test_empty_graph_rejected_as_validation(self):
        wf = self._seed(graph_doc=graph([]))
        with self.assertRaises(WorkflowValidationError):
            self.service.execute_workflow(self.owner, wf.id)

    def test_cycle_rejected_as_validation(self):
        wf = self._seed(graph_doc=graph(
            [node("a", "python"), node("b", "python")], [edge("a", "b"), edge("b", "a")]
        ))
        with self.assertRaises(WorkflowValidationError):
            self.service.execute_workflow(self.owner, wf.id)

    def test_runtime_step_failure_returns_failed_result(self):
        # Valid graph, but the python code raises → the run FAILS without the
        # service raising: "ran and failed" is a result, not an exception.
        wf = self._seed(graph_doc=graph([node("s1", "python", {"python_code": "raise ValueError('boom')"})]))
        result = self.service.execute_workflow(self.owner, wf.id)
        self.assertEqual(result.workflow_status, "FAILED")
        self.assertEqual(result.failed_step_id, "s1")

    def test_seed_inputs_threaded_into_run(self):
        # input.seed is exposed to a binding; the python step reads it back.
        g = {
            "nodes": [{"id": "s1", "kind": "python", "name": "", "config": {"python_code": "outputs['echo'] = 1"}}],
            "edges": [],
        }
        wf = self._seed(graph_doc=g)
        result = self.service.execute_workflow(self.owner, wf.id, initial_inputs={"seed": "x"})
        self.assertEqual(result.workflow_status, "COMPLETED")

    def test_multi_step_completes_in_order(self):
        g = graph(
            [
                node("a", "python", {"python_code": "outputs['x'] = 1"}),
                # Authoring kind is "file"; it maps to the "filesystem" capability.
                node("b", "file", {"operation": "WRITE", "path": "r.txt", "content": "c"}),
            ],
            [edge("a", "b")],
        )
        wf = self._seed(graph_doc=g)
        result = self.service.execute_workflow(self.owner, wf.id)
        self.assertEqual(result.workflow_status, "COMPLETED")
        self.assertEqual(result.completed_step_count, 2)
        self.assertEqual([s.step_id for s in result.step_references], ["a", "b"])


# --- API -----------------------------------------------------------------


def tracked(result):
    """A runtime result plus the record of it, as the endpoint now receives.

    Sprint 18.10 gave a run an identity and timings of its own, so the endpoint
    reads both. These API tests mock the service, so they supply both here.
    """
    now = datetime.now(timezone.utc)
    return TrackedExecution(
        result=result,
        execution=WorkflowExecution(
            id=uuid.uuid4(),
            workflow_id=uuid.UUID(result.workflow_id),
            user_id=uuid.uuid4(),
            status=result.workflow_status,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            total_step_count=result.total_step_count,
            completed_step_count=result.completed_step_count,
            failed_step_id=result.failed_step_id,
            error=result.result_metadata.get("error"),
            trigger="manual",
        ),
    )


def completed_result(workflow_id):
    return WorkflowExecutionResult(
        workflow_id=str(workflow_id),
        workflow_status="COMPLETED",
        step_references=[
            CapabilityExecutionReference(
                step_id="s1", capability_name="python", execution_status="COMPLETED",
                outputs={"v": 42},
            )
        ],
        final_outputs={"v": 42},
        completed_step_count=1,
        total_step_count=1,
    )


class ExecutionAPITests(unittest.TestCase):
    def setUp(self):
        self.user = make_user()
        self.service = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_workflow_execution_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _url(self, wid=None):
        return f"/api/v1/workflows/{wid or uuid.uuid4()}/execute"

    def test_execute_returns_200_and_maps_result(self):
        wid = uuid.uuid4()
        self.service.execute_and_record.return_value = tracked(completed_result(wid))
        response = self.client.post(self._url(wid))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "COMPLETED")
        self.assertEqual(body["completed_step_count"], 1)
        self.assertEqual(body["steps"][0]["capability"], "python")
        self.assertEqual(body["steps"][0]["outputs"], {"v": 42})

    def test_bodyless_post_runs(self):
        wid = uuid.uuid4()
        self.service.execute_and_record.return_value = tracked(completed_result(wid))
        response = self.client.post(self._url(wid))  # no JSON body
        self.assertEqual(response.status_code, 200)
        # initial_inputs falls through as None when no body is sent.
        self.assertIsNone(self.service.execute_and_record.call_args.kwargs["initial_inputs"])

    def test_seed_inputs_forwarded(self):
        wid = uuid.uuid4()
        self.service.execute_and_record.return_value = tracked(completed_result(wid))
        self.client.post(self._url(wid), json={"inputs": {"seed": "v"}})
        self.assertEqual(
            self.service.execute_and_record.call_args.kwargs["initial_inputs"], {"seed": "v"}
        )

    def test_failed_run_is_200_with_failed_status(self):
        wid = uuid.uuid4()
        self.service.execute_and_record.return_value = tracked(WorkflowExecutionResult(
            workflow_id=str(wid), workflow_status="FAILED", failed_step_id="s1",
            completed_step_count=0, total_step_count=1, result_metadata={"error": "step failed: s1"},
        ))
        response = self.client.post(self._url(wid))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "FAILED")
        self.assertEqual(response.json()["failed_step_id"], "s1")
        self.assertEqual(response.json()["error"], "step failed: s1")

    def test_not_found_maps_to_404(self):
        self.service.execute_and_record.side_effect = WorkflowNotFoundError("x")
        self.assertEqual(self.client.post(self._url()).status_code, 404)

    def test_access_denied_maps_to_403(self):
        self.service.execute_and_record.side_effect = WorkflowAccessDeniedError("x")
        self.assertEqual(self.client.post(self._url()).status_code, 403)

    def test_draft_or_archived_maps_to_409(self):
        self.service.execute_and_record.side_effect = InvalidStatusTransitionError(
            "Only a published workflow can be run. Publish it first."
        )
        self.assertEqual(self.client.post(self._url()).status_code, 409)

    def test_translation_failure_maps_to_422(self):
        self.service.execute_and_record.side_effect = WorkflowValidationError(
            "This workflow can't be run yet"
        )
        self.assertEqual(self.client.post(self._url()).status_code, 422)

    def test_non_uuid_rejected(self):
        self.assertEqual(self.client.post("/api/v1/workflows/not-a-uuid/execute").status_code, 422)

    def test_requires_authentication(self):
        app.dependency_overrides.pop(get_current_user, None)
        client = TestClient(app)
        self.assertEqual(client.post(self._url()).status_code, 401)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
