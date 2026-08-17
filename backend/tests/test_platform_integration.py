"""Platform integration tests — the domains cooperating as one (Sprint 23).

The End-to-End Platform Integration sprint added no new domain: it wired the
completed ones through the *existing* collaboration seams so the platform behaves
as one system. These tests prove that cooperation against a real in-memory
database, building on the Sprint 20 collaboration fixture (an owner, an employee,
and one resource of every collaborated type):

* G1 — task, workflow and conversation lifecycle events land on the shared
  activity timeline (``activity_events``), not just collaboration's own.
* G2 — a failed run and an AI-driven task raise real inbox notifications, with
  self-actions correctly *not* notifying.
* G3 — a confirmed conversation action becomes a task carried by the
  conversation's employee, recorded on both timelines and announced, all through
  the backend orchestrator — not a detached call.

    PYTHONPATH=. python -m unittest tests.test_platform_integration
"""

import unittest

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_conversation_action_service,
    get_current_user,
    get_workflow_coordinator,
)
from app.main import app
from app.models.activity_event import ActivityEvent
from app.models.notification import Notification
from app.models.task import Task
from app.models.workflow import Workflow
from app.schemas.task import TaskCreate
from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.notification_emitter import NotificationEmitter
from app.services.conversation_action_service import ConversationActionService
from app.services.conversation_service import ConversationService
from app.services.task_service import TaskService
from app.services.workflow_execution_history_service import (
    WorkflowExecutionHistoryService,
)
from app.services.workflow_execution_service import WorkflowExecutionService
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
    NotificationType,
    WorkflowStatus,
)

from tests.test_collaboration import CollaborationFixture


class IntegrationFixture(CollaborationFixture):
    """The Sprint 20 fixture plus session-bound emission seams."""

    def setUp(self):
        super().setUp()
        self.recorder = ActivityRecorder(self.session)
        self.notifier = NotificationEmitter(self.session)

    # --- query helpers ---------------------------------------------------

    def _events(self, resource_type, resource_id):
        return (
            self.session.query(ActivityEvent)
            .filter(
                ActivityEvent.resource_type == resource_type.value,
                ActivityEvent.resource_id == resource_id,
            )
            .all()
        )

    def _notifications(self, user_id):
        return (
            self.session.query(Notification)
            .filter(Notification.user_id == user_id)
            .all()
        )


class ActivityIntegrationTests(IntegrationFixture):
    """G1 — every domain feeds the one timeline."""

    def test_creating_a_task_records_activity(self):
        service = TaskService(self.session, None, self.recorder, self.notifier)
        task = service.create_task(self.owner, TaskCreate(name="Draft the brief"))

        events = self._events(CollaborationResourceType.TASK, task.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, ActivityKind.CREATED.value)
        self.assertEqual(events[0].owner_user_id, self.owner.id)
        # A user creating their own task must not notify them of it.
        self.assertEqual(self._notifications(self.owner.id), [])

    def test_starting_a_conversation_records_activity(self):
        service = ConversationService(self.session, self.recorder)
        conversation = service.create_conversation(
            self.owner,
            self.employee.id,
            _conversation_create("Kickoff call"),
        )
        events = self._events(
            CollaborationResourceType.CONVERSATION, conversation.id
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, ActivityKind.CREATED.value)


class WorkflowRunNotificationTests(IntegrationFixture):
    """G1 + G2 — a run lands on the workflow timeline; a failure notifies."""

    def _service(self) -> WorkflowExecutionService:
        return WorkflowExecutionService(
            self.session,
            get_workflow_coordinator(),
            WorkflowExecutionHistoryService(self.session),
            self.recorder,
            self.notifier,
        )

    def _published_workflow(self, graph) -> Workflow:
        workflow = Workflow(
            user_id=self.owner.id,
            name="Runnable",
            graph=graph,
            status=WorkflowStatus.PUBLISHED.value,
        )
        self.session.add(workflow)
        self.session.commit()
        return workflow

    def test_completed_run_records_activity_without_notifying(self):
        workflow = self._published_workflow(
            {"nodes": [_python_node("s1", "outputs['v'] = 6 * 7")], "edges": []}
        )
        tracked = self._service().execute_and_record(self.owner, workflow.id)
        self.assertEqual(tracked.result.workflow_status, "COMPLETED")

        events = self._events(CollaborationResourceType.WORKFLOW, workflow.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, ActivityKind.COMPLETED.value)
        # A completed run the owner launched is timeline-only, not inbox noise.
        self.assertEqual(self._notifications(self.owner.id), [])

    def test_failed_run_records_activity_and_notifies_the_owner(self):
        workflow = self._published_workflow(
            {"nodes": [_python_node("s1", "raise ValueError('boom')")], "edges": []}
        )
        tracked = self._service().execute_and_record(self.owner, workflow.id)
        self.assertNotEqual(tracked.result.workflow_status, "COMPLETED")

        events = self._events(CollaborationResourceType.WORKFLOW, workflow.id)
        self.assertEqual(events[0].kind, ActivityKind.UPDATED.value)

        notes = self._notifications(self.owner.id)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].type, NotificationType.WORKFLOW.value)
        # A failure is a platform event, not a self-action.
        self.assertEqual(notes[0].actor_type, ActivityActorType.SYSTEM.value)


class ConversationActionTests(IntegrationFixture):
    """G3 — a confirmed action becomes a linked, announced task."""

    def _service(self) -> ConversationActionService:
        return ConversationActionService(
            self.session,
            TaskService(self.session),
            self.recorder,
            self.notifier,
        )

    def test_action_creates_task_carried_by_the_employee(self):
        task = self._service().create_task_from_conversation(
            self.owner,
            self.conversation.id,
            "Send email",
            "Email Cody the launch summary",
        )
        stored = self.session.query(Task).filter(Task.id == task.id).one()
        self.assertEqual(stored.user_id, self.owner.id)
        # The task is carried by the conversation's employee, not orphaned.
        self.assertEqual(stored.employee_id, self.employee.id)
        self.assertIn("Send email", stored.name)

    def test_action_records_both_timelines_and_notifies(self):
        task = self._service().create_task_from_conversation(
            self.owner, self.conversation.id, "Create task", "Follow up on the RFP"
        )

        task_events = self._events(CollaborationResourceType.TASK, task.id)
        self.assertEqual(len(task_events), 1)
        self.assertEqual(task_events[0].kind, ActivityKind.CREATED.value)
        self.assertEqual(
            task_events[0].actor_type, ActivityActorType.EMPLOYEE.value
        )

        convo_events = self._events(
            CollaborationResourceType.CONVERSATION, self.conversation.id
        )
        self.assertEqual(len(convo_events), 1)
        self.assertEqual(convo_events[0].kind, ActivityKind.ASSIGNED.value)

        notes = self._notifications(self.owner.id)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].type, NotificationType.TASK.value)
        # The AI employee did it for the owner, so the owner is notified.
        self.assertEqual(notes[0].actor_type, ActivityActorType.EMPLOYEE.value)


class ConversationActionAPITests(IntegrationFixture):
    """G3 through the endpoint — the router wiring and 404 mapping."""

    def setUp(self):
        super().setUp()
        app.dependency_overrides[get_current_user] = lambda: self.owner
        app.dependency_overrides[get_conversation_action_service] = (
            lambda: ConversationActionService(
                self.session,
                TaskService(self.session),
                self.recorder,
                self.notifier,
            )
        )
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_endpoint_creates_a_linked_task(self):
        response = self.client.post(
            f"/api/v1/conversations/{self.conversation.id}/actions",
            json={"label": "Schedule", "summary": "Book the review for Friday"},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["business_id"].startswith("TSK-"))
        self.assertEqual(body["employee_id"], str(self.employee.id))

    def test_unknown_conversation_is_404(self):
        import uuid

        response = self.client.post(
            f"/api/v1/conversations/{uuid.uuid4()}/actions",
            json={"label": "Send email", "summary": "Anything"},
        )
        self.assertEqual(response.status_code, 404)


# --- helpers -------------------------------------------------------------


def _python_node(node_id: str, code: str) -> dict:
    return {
        "id": node_id,
        "kind": "python",
        "name": "",
        "config": {"python_code": code},
    }


def _conversation_create(title: str):
    from app.schemas.conversation import ConversationCreate

    return ConversationCreate(title=title)


if __name__ == "__main__":
    unittest.main()
