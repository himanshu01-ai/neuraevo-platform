"""Collaboration activity tests — the reusable timeline (Sprint 20C).

Builds on the Sprint 20A fixture and exercises the activity timeline end to end:
participant and sharing actions emit events; the resource timeline and the
per-user feed read them back, permission-aware, against a real in-memory
database.

    PYTHONPATH=. python -m unittest tests.test_collaboration_activity
"""

import unittest

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_activity_service,
    get_collaboration_service,
    get_current_user,
    get_sharing_service,
)
from app.main import app
from app.schemas.collaboration import ParticipantCreate
from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.activity_service import (
    ActivityScope,
    ActivityService,
)
from app.services.collaboration.service import (
    CollaborationService,
    ResourceNotFoundError,
)
from app.services.collaboration.sharing_service import SharingService
from app.utils.constants import (
    ActivityKind,
    CollaborationResourceType,
    CollaborationRole,
    ParticipantType,
)

from tests.test_collaboration import CollaborationFixture


class ActivityRecordingTests(CollaborationFixture):
    """Actions emit events; the timeline reads them back."""

    def setUp(self):
        super().setUp()
        self.recorder = ActivityRecorder(self.session)
        # Recorder-attached services, as the DI factories build them.
        self.collab = CollaborationService(self.session, self.recorder)
        self.sharing = SharingService(self.session, self.recorder)
        self.activity = ActivityService(self.session)

    def _add(self, rtype, rid, role=CollaborationRole.VIEWER):
        return self.collab.add_participant(
            self.owner,
            rtype,
            rid,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
                role=role,
            ),
        )

    def test_adding_a_participant_records_an_event(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        self._add(rtype, rid)
        events = self.activity.list_for_resource(self.owner, rtype, rid)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, ActivityKind.PARTICIPANT_ADDED)
        self.assertEqual(events[0].actor_name, "Olivia Owner")
        self.assertTrue(events[0].is_own)  # the owner did it

    def test_role_change_and_removal_record_events(self):
        rtype, rid = CollaborationResourceType.WORKFLOW, self.workflow.id
        added = self._add(rtype, rid)
        self.collab.update_participant_role(
            self.owner, rtype, rid, added.id, CollaborationRole.EDITOR
        )
        self.collab.remove_participant(self.owner, rtype, rid, added.id)
        events = self.activity.list_for_resource(self.owner, rtype, rid)
        kinds = [e.kind for e in events]
        # Newest first: removed, role_changed, participant_added.
        self.assertEqual(
            kinds,
            [
                ActivityKind.PARTICIPANT_REMOVED,
                ActivityKind.ROLE_CHANGED,
                ActivityKind.PARTICIPANT_ADDED,
            ],
        )

    def test_sharing_and_joining_record_events(self):
        rtype, rid = CollaborationResourceType.CONVERSATION, self.conversation.id
        _, token = self.sharing.create_share(
            self.owner, rtype, rid, CollaborationRole.EDITOR
        )
        self.sharing.redeem(self.collaborator, token)
        events = self.activity.list_for_resource(self.owner, rtype, rid)
        kinds = {e.kind for e in events}
        self.assertIn(ActivityKind.SHARED, kinds)
        self.assertIn(ActivityKind.JOINED, kinds)

    def test_resource_timeline_is_permission_aware(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        self._add(rtype, rid)
        # The added collaborator (viewer) can read the timeline...
        self.assertTrue(self.activity.list_for_resource(self.collaborator, rtype, rid))
        # ...the outsider cannot even see the resource.
        with self.assertRaises(ResourceNotFoundError):
            self.activity.list_for_resource(self.outsider, rtype, rid)

    def test_user_feed_spans_owned_and_participant_resources(self):
        # Owner acts on a task and a workflow.
        self._add(CollaborationResourceType.TASK, self.task.id)
        self._add(CollaborationResourceType.WORKFLOW, self.workflow.id)

        owner_feed = self.activity.list_for_user(self.owner)
        self.assertGreaterEqual(len(owner_feed), 2)

        # The collaborator participates in both, so their feed sees the events too.
        collab_feed = self.activity.list_for_user(self.collaborator)
        self.assertTrue(collab_feed)
        # But none of them are the collaborator's own doing.
        mine = self.activity.list_for_user(
            self.collaborator, scope=ActivityScope.MINE
        )
        self.assertEqual(mine, [])

    def test_mine_scope_is_the_actors_own_events(self):
        self._add(CollaborationResourceType.TASK, self.task.id)
        mine = self.activity.list_for_user(self.owner, scope=ActivityScope.MINE)
        self.assertTrue(mine)
        self.assertTrue(all(e.is_own for e in mine))


class ActivityAPITests(CollaborationFixture):
    """The activity endpoints end-to-end, over the same real session."""

    def setUp(self):
        super().setUp()
        self._current_user = self.owner
        recorder = ActivityRecorder(self.session)
        app.dependency_overrides[get_current_user] = lambda: self._current_user
        app.dependency_overrides[get_collaboration_service] = (
            lambda: CollaborationService(self.session, recorder)
        )
        app.dependency_overrides[get_sharing_service] = (
            lambda: SharingService(self.session, recorder)
        )
        app.dependency_overrides[get_activity_service] = (
            lambda: ActivityService(self.session)
        )
        self.client = TestClient(app)

    def test_resource_timeline_endpoint(self):
        # Owner adds a participant, generating an event.
        self.client.post(
            f"/api/v1/collaboration/task/{self.task.id}/participants",
            json={"participant_type": "user", "user_id": str(self.collaborator.id)},
        )
        resp = self.client.get(
            f"/api/v1/collaboration/task/{self.task.id}/activity"
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertEqual(rows[0]["kind"], "participant_added")
        self.assertTrue(rows[0]["is_own"])

    def test_feed_endpoint(self):
        self.client.post(
            f"/api/v1/collaboration/workflow/{self.workflow.id}/participants",
            json={"participant_type": "user", "user_id": str(self.collaborator.id)},
        )
        resp = self.client.get("/api/v1/collaboration/activity")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.json()) >= 1)

    def test_outsider_cannot_read_timeline(self):
        self._current_user = self.outsider
        resp = self.client.get(
            f"/api/v1/collaboration/task/{self.task.id}/activity"
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
