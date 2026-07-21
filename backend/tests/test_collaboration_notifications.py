"""Collaboration notification tests — the inbox (Sprint 20D).

Builds on the Sprint 20A fixture and exercises the notification architecture end
to end: participant and sharing actions raise notifications for the right
recipient; the inbox reads, toggles, counts, and clears them, all scoped to the
owning user, against a real in-memory database.

    PYTHONPATH=. python -m unittest tests.test_collaboration_notifications
"""

import unittest

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_collaboration_service,
    get_current_user,
    get_notification_service,
    get_sharing_service,
)
from app.main import app
from app.schemas.collaboration import NotificationUpdate, ParticipantCreate
from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.notification_emitter import NotificationEmitter
from app.services.collaboration.notification_service import (
    NotificationNotFoundError,
    NotificationService,
)
from app.services.collaboration.service import CollaborationService
from app.services.collaboration.sharing_service import SharingService
from app.utils.constants import (
    CollaborationResourceType,
    CollaborationRole,
    NotificationType,
    ParticipantType,
)

from tests.test_collaboration import CollaborationFixture


class NotificationEmissionTests(CollaborationFixture):
    """Collaboration actions raise notifications for the right recipient."""

    def setUp(self):
        super().setUp()
        emitter = NotificationEmitter(self.session)
        recorder = ActivityRecorder(self.session)
        self.collab = CollaborationService(self.session, recorder, emitter)
        self.sharing = SharingService(self.session, recorder, emitter)
        self.notifications = NotificationService(self.session)

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

    def test_being_added_notifies_the_participant(self):
        self._add(CollaborationResourceType.TASK, self.task.id)
        inbox = self.notifications.list_for_user(self.collaborator)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0].type, NotificationType.TASK)
        self.assertFalse(inbox[0].read)
        self.assertEqual(inbox[0].actor_name, "Olivia Owner")
        # The owner is not notified about their own action.
        self.assertEqual(self.notifications.list_for_user(self.owner), [])

    def test_adding_an_employee_notifies_no_one(self):
        self.collab.add_participant(
            self.owner,
            CollaborationResourceType.TASK,
            self.task.id,
            ParticipantCreate(
                participant_type=ParticipantType.EMPLOYEE,
                employee_id=self.employee.id,
            ),
        )
        # No user recipient — an employee has no inbox.
        self.assertEqual(self.notifications.list_for_user(self.owner), [])
        self.assertEqual(self.notifications.list_for_user(self.collaborator), [])

    def test_role_change_notifies_the_participant(self):
        added = self._add(CollaborationResourceType.WORKFLOW, self.workflow.id)
        self.collab.update_participant_role(
            self.owner,
            CollaborationResourceType.WORKFLOW,
            self.workflow.id,
            added.id,
            CollaborationRole.EDITOR,
        )
        inbox = self.notifications.list_for_user(self.collaborator)
        # Added + role changed.
        self.assertEqual(len(inbox), 2)

    def test_join_via_share_notifies_the_owner(self):
        _, token = self.sharing.create_share(
            self.owner,
            CollaborationResourceType.CONVERSATION,
            self.conversation.id,
            CollaborationRole.VIEWER,
        )
        self.sharing.redeem(self.collaborator, token)
        owner_inbox = self.notifications.list_for_user(self.owner)
        self.assertEqual(len(owner_inbox), 1)
        self.assertIn("joined", owner_inbox[0].title.lower())
        self.assertEqual(owner_inbox[0].actor_name, "Cody Collaborator")


class NotificationInboxTests(CollaborationFixture):
    """Reading, toggling, counting, and clearing the inbox."""

    def setUp(self):
        super().setUp()
        emitter = NotificationEmitter(self.session)
        self.collab = CollaborationService(
            self.session, ActivityRecorder(self.session), emitter
        )
        self.notifications = NotificationService(self.session)
        # Generate a couple of notifications for the collaborator.
        for rtype, rid in (
            (CollaborationResourceType.TASK, self.task.id),
            (CollaborationResourceType.WORKFLOW, self.workflow.id),
        ):
            self.collab.add_participant(
                self.owner,
                rtype,
                rid,
                ParticipantCreate(
                    participant_type=ParticipantType.USER,
                    user_id=self.collaborator.id,
                ),
            )

    def test_counts_reflect_unread_and_bookmarked(self):
        counts = self.notifications.counts(self.collaborator)
        self.assertEqual(counts.unread, 2)
        self.assertEqual(counts.bookmarked, 0)

    def test_toggle_flags_are_scoped_and_applied(self):
        inbox = self.notifications.list_for_user(self.collaborator)
        target = inbox[0]
        updated = self.notifications.update(
            self.collaborator,
            target.id,
            NotificationUpdate(read=True, bookmarked=True),
        )
        self.assertTrue(updated.read)
        self.assertTrue(updated.bookmarked)
        counts = self.notifications.counts(self.collaborator)
        self.assertEqual(counts.unread, 1)
        self.assertEqual(counts.bookmarked, 1)

    def test_another_user_cannot_touch_your_notification(self):
        target = self.notifications.list_for_user(self.collaborator)[0]
        with self.assertRaises(NotificationNotFoundError):
            self.notifications.get(self.outsider, target.id)
        with self.assertRaises(NotificationNotFoundError):
            self.notifications.update(
                self.outsider, target.id, NotificationUpdate(read=True)
            )

    def test_mark_all_read(self):
        self.notifications.mark_all_read(self.collaborator)
        self.assertEqual(self.notifications.counts(self.collaborator).unread, 0)

    def test_archive_hides_from_default_list(self):
        target = self.notifications.list_for_user(self.collaborator)[0]
        self.notifications.update(
            self.collaborator, target.id, NotificationUpdate(archived=True)
        )
        self.assertEqual(len(self.notifications.list_for_user(self.collaborator)), 1)
        self.assertEqual(
            len(
                self.notifications.list_for_user(
                    self.collaborator, include_archived=True
                )
            ),
            2,
        )


class NotificationAPITests(CollaborationFixture):
    """The notification endpoints end-to-end, over the same real session."""

    def setUp(self):
        super().setUp()
        self._current_user = self.owner
        emitter = NotificationEmitter(self.session)
        app.dependency_overrides[get_current_user] = lambda: self._current_user
        app.dependency_overrides[get_collaboration_service] = (
            lambda: CollaborationService(
                self.session, ActivityRecorder(self.session), emitter
            )
        )
        app.dependency_overrides[get_notification_service] = (
            lambda: NotificationService(self.session)
        )
        self.client = TestClient(app)
        # Owner adds the collaborator, raising a notification for them.
        self.client.post(
            f"/api/v1/collaboration/task/{self.task.id}/participants",
            json={"participant_type": "user", "user_id": str(self.collaborator.id)},
        )

    def test_list_and_counts(self):
        self._current_user = self.collaborator
        listed = self.client.get("/api/v1/collaboration/notifications")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

        counts = self.client.get("/api/v1/collaboration/notifications/counts")
        self.assertEqual(counts.status_code, 200)
        self.assertEqual(counts.json()["unread"], 1)

    def test_patch_marks_read(self):
        self._current_user = self.collaborator
        notification_id = self.client.get(
            "/api/v1/collaboration/notifications"
        ).json()[0]["id"]
        patched = self.client.patch(
            f"/api/v1/collaboration/notifications/{notification_id}",
            json={"read": True},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertTrue(patched.json()["read"])
        self.assertEqual(
            self.client.get(
                "/api/v1/collaboration/notifications/counts"
            ).json()["unread"],
            0,
        )

    def test_read_all(self):
        self._current_user = self.collaborator
        resp = self.client.post("/api/v1/collaboration/notifications/read-all")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(n["read"] for n in resp.json()))

    def test_counts_route_not_shadowed_by_id_route(self):
        # `/notifications/counts` must resolve to the counts endpoint, never be
        # parsed as a notification id.
        self._current_user = self.collaborator
        resp = self.client.get("/api/v1/collaboration/notifications/counts")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("unread", resp.json())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
