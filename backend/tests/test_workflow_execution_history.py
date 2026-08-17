"""Workflow execution history tests (Sprint 18.10).

Runs against a real in-memory SQLite database, not a fake session: the point of
this sprint is that a run is *persisted*, and a fake that accepts every write
would prove nothing about whether it can be read back.

* ``RecorderTests`` — the timing seam, and that wrapping the router changes
  nothing about what the coordinator does.
* ``RecordingTests`` — what a finished run leaves behind, including the pieces
  the live response has always discarded.
* ``HistoryReadTests`` — listing and detail, and who is allowed to see them.
* ``RetryTests`` — a retry creates a new run and leaves the old one alone.
* ``HistoryAPITests`` — the three endpoints, and that the existing execute
  response is still what it was plus new fields.

Runnable with stdlib unittest:
    PYTHONPATH=. python -m unittest tests.test_workflow_execution_history
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.dependencies import (
    get_current_user,
    get_workflow_execution_history_service,
    get_workflow_execution_service,
)
from app.main import app
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.services.runtime.execution_capability_models import CapabilityExecutionRequest
from app.services.runtime.workflow_models import (
    CapabilityExecutionReference,
    WorkflowArtifactReference,
    WorkflowExecutionResult,
)
from app.services.workflow_execution_history_service import (
    TRIGGER_MANUAL,
    TRIGGER_RETRY,
    ExecutionAccessDeniedError,
    ExecutionNotFoundError,
    WorkflowExecutionHistoryService,
)
from app.services.workflow_execution_recorder import (
    ExecutionLog,
    TimingCapabilityRouter,
)
from app.services.workflow_execution_service import WorkflowExecutionService
from app.utils.constants import WorkflowStatus

from app.core.dependencies import get_workflow_coordinator

# --- fixtures ------------------------------------------------------------

PYTHON_GRAPH = {
    "nodes": [
        {
            "id": "s1",
            "kind": "python",
            "name": "Compute",
            "config": {"python_code": "outputs['v'] = 6 * 7"},
        }
    ],
    "edges": [],
}

FAILING_GRAPH = {
    "nodes": [
        {
            "id": "s1",
            "kind": "python",
            "name": "Explode",
            "config": {"python_code": "raise ValueError('boom')"},
        }
    ],
    "edges": [],
}


def _naive(moment: datetime) -> datetime:
    """The same instant without its timezone, for comparing across a round trip.

    SQLite has no timezone type, so a value written as UTC-aware reads back
    naive. PostgreSQL's ``timestamptz`` keeps it. The instant is identical either
    way, and it is the instant these tests are about.
    """
    return moment.replace(tzinfo=None)


def make_engine():
    """A fresh in-memory database with every table this domain needs."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


class DatabaseTestCase(unittest.TestCase):
    """A real session, a real user, and a real published workflow."""

    def setUp(self):
        self.engine = make_engine()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session: Session = self.Session()

        self.owner = User(
            id=uuid.uuid4(),
            email="owner@neuraevo.dev",
            hashed_password="x",
            full_name="Owner",
            is_active=True,
        )
        self.other = User(
            id=uuid.uuid4(),
            email="other@neuraevo.dev",
            hashed_password="x",
            full_name="Other",
            is_active=True,
        )
        self.session.add_all([self.owner, self.other])
        self.session.commit()

        self.workflow = self._add_workflow(PYTHON_GRAPH)
        self.history = WorkflowExecutionHistoryService(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _add_workflow(self, graph, owner=None, status=WorkflowStatus.PUBLISHED.value):
        workflow = Workflow(
            id=uuid.uuid4(),
            user_id=(owner or self.owner).id,
            name=f"Runnable {uuid.uuid4().hex[:6]}",
            description=None,
            graph=graph,
            status=status,
        )
        self.session.add(workflow)
        self.session.commit()
        return workflow

    def _service(self):
        return WorkflowExecutionService(
            self.session,
            get_workflow_coordinator(),
            WorkflowExecutionHistoryService(self.session),
        )


# --- the timing seam -----------------------------------------------------


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.inner = get_workflow_coordinator().router
        self.recorder = TimingCapabilityRouter(self.inner)

    def _request(self, step_id="s1"):
        return CapabilityExecutionRequest(
            runtime_id="t",
            execution_id="t",
            execution_unit_id=step_id,
            capability_name="python",
            capability_inputs={"python_code": "outputs['v'] = 1"},
        )

    def test_dispatch_returns_what_the_router_returns(self):
        """Wrapping must not change the run — only observe it."""
        direct = self.inner.dispatch(self._request())
        through = self.recorder.dispatch(self._request())
        self.assertEqual(direct.execution_status, through.execution_status)
        self.assertEqual(direct.capability_outputs, through.capability_outputs)

    def test_timing_is_recorded_per_step(self):
        self.recorder.dispatch(self._request("alpha"))
        timing = self.recorder.timing_for("alpha")
        self.assertIsNotNone(timing)
        self.assertGreaterEqual(timing.duration_ms, 0)
        self.assertLessEqual(timing.started_at, timing.finished_at)

    def test_untouched_step_has_no_timing(self):
        self.assertIsNone(self.recorder.timing_for("never-ran"))

    def test_availability_still_answers_from_the_real_router(self):
        self.assertTrue(self.recorder.is_available("python"))
        self.assertFalse(self.recorder.is_available("teleport"))
        self.assertEqual(
            self.recorder.available_capabilities(), self.inner.available_capabilities()
        )

    def test_a_failing_dispatch_is_still_timed(self):
        """A failed step is exactly the one whose timing explains something."""
        bad = CapabilityExecutionRequest(
            runtime_id="t",
            execution_id="t",
            execution_unit_id="boom",
            capability_name="does-not-exist",
            capability_inputs={},
        )
        with self.assertRaises(Exception):
            self.recorder.dispatch(bad)
        self.assertIsNotNone(self.recorder.timing_for("boom"))


# --- recording -----------------------------------------------------------


class RecordingTests(DatabaseTestCase):
    def test_a_successful_run_is_recorded(self):
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)

        self.assertEqual(tracked.result.workflow_status, "COMPLETED")
        execution = tracked.execution
        self.assertEqual(execution.workflow_id, self.workflow.id)
        self.assertEqual(execution.user_id, self.owner.id)
        self.assertEqual(execution.status, "COMPLETED")
        self.assertEqual(execution.trigger, TRIGGER_MANUAL)
        self.assertIsNone(execution.retry_of_execution_id)
        self.assertGreaterEqual(execution.duration_ms, 0)
        self.assertLessEqual(execution.started_at, execution.finished_at)

    def test_a_failed_run_is_recorded_with_its_reason(self):
        workflow = self._add_workflow(FAILING_GRAPH)
        tracked = self._service().execute_and_record(self.owner, workflow.id)

        execution = tracked.execution
        self.assertEqual(execution.status, "FAILED")
        self.assertEqual(execution.failed_step_id, "s1")
        self.assertTrue(execution.error)
        self.assertEqual(execution.completed_step_count, 0)

    def test_each_run_gets_its_own_identity(self):
        """Two runs of one workflow used to be indistinguishable."""
        service = self._service()
        first = service.execute_and_record(self.owner, self.workflow.id).execution
        second = service.execute_and_record(self.owner, self.workflow.id).execution
        self.assertNotEqual(first.id, second.id)

    def test_steps_are_persisted_with_timings(self):
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)
        execution = self.history.get_execution(self.owner, tracked.execution.id)

        self.assertEqual(len(execution.steps), 1)
        step = execution.steps[0]
        self.assertEqual(step.step_id, "s1")
        self.assertEqual(step.capability, "python")
        self.assertEqual(step.status, "COMPLETED")
        self.assertEqual(step.position, 0)
        self.assertIsNotNone(step.started_at)
        self.assertIsNotNone(step.finished_at)
        self.assertGreaterEqual(step.duration_ms, 0)

    def test_step_outputs_are_persisted(self):
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)
        execution = self.history.get_execution(self.owner, tracked.execution.id)
        self.assertEqual(execution.steps[0].outputs["execution_outputs"], {"v": 42})

    def test_step_metadata_is_kept_rather_than_discarded(self):
        """The live response has dropped this since Sprint 18.6."""
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)
        execution = self.history.get_execution(self.owner, tracked.execution.id)
        self.assertIsInstance(execution.steps[0].step_metadata, dict)

    def test_logs_are_structured_records(self):
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)
        execution = self.history.get_execution(self.owner, tracked.execution.id)

        self.assertTrue(execution.logs)
        levels = {log.level for log in execution.logs}
        self.assertTrue(levels <= {"info", "warning", "error"})
        self.assertEqual(
            [log.sequence for log in execution.logs],
            list(range(len(execution.logs))),
        )

    def test_a_failed_run_logs_an_error(self):
        workflow = self._add_workflow(FAILING_GRAPH)
        tracked = self._service().execute_and_record(self.owner, workflow.id)
        execution = self.history.get_execution(self.owner, tracked.execution.id)

        errors = [log for log in execution.logs if log.level == "error"]
        self.assertTrue(errors)

    def test_logs_never_carry_a_traceback(self):
        """An internal traceback describes the server, not the workflow."""
        workflow = self._add_workflow(FAILING_GRAPH)
        tracked = self._service().execute_and_record(self.owner, workflow.id)
        execution = self.history.get_execution(self.owner, tracked.execution.id)

        for log in execution.logs:
            self.assertNotIn("Traceback", log.message)
            self.assertNotIn("File \"", log.message)
            self.assertNotIn(".py", log.message)

    def test_a_refused_run_is_not_recorded(self):
        """Nothing ran, so there is no run to remember."""
        draft = self._add_workflow(PYTHON_GRAPH, status=WorkflowStatus.DRAFT.value)
        with self.assertRaises(Exception):
            self._service().execute_and_record(self.owner, draft.id)

        rows, total = self.history.list_for_workflow(self.owner, draft.id)
        self.assertEqual(total, 0)
        self.assertEqual(list(rows), [])

    def test_artifact_descriptors_are_stored_without_contents(self):
        execution = self.history.record(
            owner=self.owner,
            workflow_id=self.workflow.id,
            result=WorkflowExecutionResult(
                workflow_id=str(self.workflow.id),
                workflow_status="COMPLETED",
                step_references=[
                    CapabilityExecutionReference(
                        step_id="s1",
                        capability_name="filesystem",
                        execution_status="COMPLETED",
                        artifact_reference_ids=["s1:a1"],
                    )
                ],
                artifacts=[
                    WorkflowArtifactReference(
                        reference_id="s1:a1",
                        artifact_id="a1",
                        artifact_type="CREATED",
                        name="report.txt",
                        source_step="s1",
                        source_capability="filesystem",
                        path="/tmp/secret/report.txt",
                    )
                ],
                completed_step_count=1,
                total_step_count=1,
            ),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

        artifacts = execution.steps[0].artifacts
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["name"], "report.txt")
        # A descriptor, not a copy — and not a description of the server.
        self.assertNotIn("path", artifacts[0])

    def test_duration_is_never_negative(self):
        """A clock that steps backwards must not store an impossible run."""
        now = datetime.now(timezone.utc)
        execution = self.history.record(
            owner=self.owner,
            workflow_id=self.workflow.id,
            result=WorkflowExecutionResult(
                workflow_id=str(self.workflow.id), workflow_status="COMPLETED"
            ),
            started_at=now,
            finished_at=now - timedelta(seconds=5),
        )
        self.assertEqual(execution.duration_ms, 0)


# --- reading -------------------------------------------------------------


class HistoryReadTests(DatabaseTestCase):
    def test_history_is_newest_first(self):
        service = self._service()
        first = service.execute_and_record(self.owner, self.workflow.id).execution
        second = service.execute_and_record(self.owner, self.workflow.id).execution

        rows, total = self.history.list_for_workflow(self.owner, self.workflow.id)
        self.assertEqual(total, 2)
        self.assertEqual([r.id for r in rows], [second.id, first.id])

    def test_history_is_scoped_to_its_workflow(self):
        other_workflow = self._add_workflow(PYTHON_GRAPH)
        service = self._service()
        service.execute_and_record(self.owner, self.workflow.id)
        service.execute_and_record(self.owner, other_workflow.id)

        _, total = self.history.list_for_workflow(self.owner, self.workflow.id)
        self.assertEqual(total, 1)

    def test_empty_history_is_empty_not_missing(self):
        rows, total = self.history.list_for_workflow(self.owner, self.workflow.id)
        self.assertEqual(total, 0)
        self.assertEqual(list(rows), [])

    def test_listing_respects_paging(self):
        service = self._service()
        for _ in range(3):
            service.execute_and_record(self.owner, self.workflow.id)

        rows, total = self.history.list_for_workflow(
            self.owner, self.workflow.id, skip=1, limit=1
        )
        self.assertEqual(total, 3)
        self.assertEqual(len(rows), 1)

    def test_another_users_history_is_refused(self):
        from app.services.workflow_service import WorkflowAccessDeniedError

        self._service().execute_and_record(self.owner, self.workflow.id)
        with self.assertRaises(WorkflowAccessDeniedError):
            self.history.list_for_workflow(self.other, self.workflow.id)

    def test_detail_carries_steps_and_logs(self):
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)
        execution = self.history.get_execution(self.owner, tracked.execution.id)
        self.assertTrue(execution.steps)
        self.assertTrue(execution.logs)

    def test_unknown_execution_is_not_found(self):
        with self.assertRaises(ExecutionNotFoundError):
            self.history.get_execution(self.owner, uuid.uuid4())

    def test_another_users_execution_is_refused(self):
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)
        with self.assertRaises(ExecutionAccessDeniedError):
            self.history.get_execution(self.other, tracked.execution.id)


# --- retry ---------------------------------------------------------------


class RetryTests(DatabaseTestCase):
    def test_retry_creates_a_new_execution(self):
        service = self._service()
        original = service.execute_and_record(self.owner, self.workflow.id).execution
        retried = service.execute_and_record(
            self.owner,
            self.workflow.id,
            trigger=TRIGGER_RETRY,
            retry_of_execution_id=original.id,
        ).execution

        self.assertNotEqual(retried.id, original.id)
        self.assertEqual(retried.trigger, TRIGGER_RETRY)
        self.assertEqual(retried.retry_of_execution_id, original.id)

    def test_retry_leaves_the_original_untouched(self):
        """History is immutable: a retry points at the past, never edits it."""
        service = self._service()
        original = service.execute_and_record(self.owner, self.workflow.id).execution
        before = (
            original.status,
            _naive(original.started_at),
            _naive(original.finished_at),
            original.duration_ms,
            original.trigger,
        )

        service.execute_and_record(
            self.owner,
            self.workflow.id,
            trigger=TRIGGER_RETRY,
            retry_of_execution_id=original.id,
        )

        self.session.expire_all()
        reloaded = self.session.get(WorkflowExecution, original.id)
        self.assertEqual(
            (
                reloaded.status,
                _naive(reloaded.started_at),
                _naive(reloaded.finished_at),
                reloaded.duration_ms,
                reloaded.trigger,
            ),
            before,
        )
        self.assertIsNone(reloaded.retry_of_execution_id)

    def test_retrying_a_failure_can_still_fail(self):
        workflow = self._add_workflow(FAILING_GRAPH)
        service = self._service()
        original = service.execute_and_record(self.owner, workflow.id).execution
        retried = service.execute_and_record(
            self.owner,
            workflow.id,
            trigger=TRIGGER_RETRY,
            retry_of_execution_id=original.id,
        ).execution

        self.assertEqual(original.status, "FAILED")
        self.assertEqual(retried.status, "FAILED")
        self.assertEqual(retried.retry_of_execution_id, original.id)

    def test_history_shows_both_the_original_and_the_retry(self):
        service = self._service()
        original = service.execute_and_record(self.owner, self.workflow.id).execution
        service.execute_and_record(
            self.owner,
            self.workflow.id,
            trigger=TRIGGER_RETRY,
            retry_of_execution_id=original.id,
        )
        _, total = self.history.list_for_workflow(self.owner, self.workflow.id)
        self.assertEqual(total, 2)

    def test_retry_of_an_unknown_execution_is_not_found(self):
        with self.assertRaises(ExecutionNotFoundError):
            self.history.get_for_retry(self.owner, uuid.uuid4())

    def test_retry_of_another_users_execution_is_refused(self):
        tracked = self._service().execute_and_record(self.owner, self.workflow.id)
        with self.assertRaises(ExecutionAccessDeniedError):
            self.history.get_for_retry(self.other, tracked.execution.id)


# --- API -----------------------------------------------------------------


class HistoryAPITests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[get_current_user] = lambda: self.owner
        app.dependency_overrides[get_workflow_execution_service] = self._service
        app.dependency_overrides[get_workflow_execution_history_service] = (
            lambda: WorkflowExecutionHistoryService(self.session)
        )
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        super().tearDown()

    def _run(self):
        return self.client.post(f"/api/v1/workflows/{self.workflow.id}/execute")

    def test_execute_response_keeps_every_field_it_had(self):
        """Sprint 18.10 is additive: an existing caller reads this unchanged."""
        body = self._run().json()
        for field in (
            "workflow_id",
            "status",
            "completed_step_count",
            "total_step_count",
            "failed_step_id",
            "steps",
            "final_outputs",
            "error",
        ):
            self.assertIn(field, body)

    def test_execute_response_now_identifies_the_run(self):
        body = self._run().json()
        self.assertIn("execution_id", body)
        self.assertIn("started_at", body)
        self.assertIn("duration_ms", body)

    def test_listing_a_workflows_runs(self):
        self._run()
        self._run()
        body = self.client.get(
            f"/api/v1/workflows/{self.workflow.id}/executions"
        ).json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(len(body["items"]), 2)

    def test_listing_an_unrun_workflow_is_empty(self):
        body = self.client.get(
            f"/api/v1/workflows/{self.workflow.id}/executions"
        ).json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["items"], [])

    def test_listing_another_users_workflow_is_forbidden(self):
        foreign = self._add_workflow(PYTHON_GRAPH, owner=self.other)
        response = self.client.get(f"/api/v1/workflows/{foreign.id}/executions")
        self.assertEqual(response.status_code, 403)

    def test_execution_detail(self):
        execution_id = self._run().json()["execution_id"]
        body = self.client.get(f"/api/v1/workflow-executions/{execution_id}").json()

        self.assertEqual(body["id"], execution_id)
        self.assertEqual(body["status"], "COMPLETED")
        self.assertEqual(len(body["steps"]), 1)
        self.assertTrue(body["logs"])
        self.assertEqual(body["steps"][0]["capability"], "python")

    def test_unknown_execution_is_404(self):
        response = self.client.get(f"/api/v1/workflow-executions/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 404)

    def test_retry_creates_a_new_run(self):
        original_id = self._run().json()["execution_id"]
        response = self.client.post(
            f"/api/v1/workflow-executions/{original_id}/retry"
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertNotEqual(body["execution_id"], original_id)

        detail = self.client.get(
            f"/api/v1/workflow-executions/{body['execution_id']}"
        ).json()
        self.assertEqual(detail["trigger"], "retry")
        self.assertEqual(detail["retry_of_execution_id"], original_id)

    def test_retry_of_an_unknown_execution_is_404(self):
        response = self.client.post(
            f"/api/v1/workflow-executions/{uuid.uuid4()}/retry"
        )
        self.assertEqual(response.status_code, 404)

    def test_retry_is_refused_once_the_workflow_is_unpublished(self):
        """A retry runs the workflow as it is now, not as it was."""
        execution_id = self._run().json()["execution_id"]
        self.workflow.status = WorkflowStatus.DRAFT.value
        self.session.commit()

        response = self.client.post(
            f"/api/v1/workflow-executions/{execution_id}/retry"
        )
        self.assertEqual(response.status_code, 409)

    def test_history_survives_the_request_that_made_it(self):
        """The whole point: a run is still there after its response is gone."""
        execution_id = self._run().json()["execution_id"]
        self.session.expire_all()
        self.assertEqual(
            self.client.get(f"/api/v1/workflow-executions/{execution_id}").status_code,
            200,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
