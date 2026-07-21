"""Collaboration sharing tests — secure share links (Sprint 20B).

Builds on the Sprint 20A fixture (owner, collaborator, outsider, employees, one
resource of every type) and exercises the sharing architecture against a real
in-memory database: minting links, listing and revoking them, and redeeming a
token into first-class participation through the reused collaboration core.

    PYTHONPATH=. python -m unittest tests.test_collaboration_sharing
"""

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_collaboration_service,
    get_current_user,
    get_sharing_service,
)
from app.core.security import hash_secret
from app.main import app
from app.services.collaboration.service import (
    CollaborationAccessDeniedError,
    CollaborationService,
    ResourceNotFoundError,
)
from app.services.collaboration.sharing_service import (
    ShareInactiveError,
    ShareNotFoundError,
    SharingService,
)
from app.utils.constants import CollaborationResourceType, CollaborationRole

from tests.test_collaboration import CollaborationFixture


class SharingServiceTests(CollaborationFixture):
    """Minting, listing, revoking, and redeeming share links."""

    def setUp(self):
        super().setUp()
        self.sharing = SharingService(self.session)

    # --- Creation --------------------------------------------------------

    def test_owner_creates_share_and_token_is_only_the_hash_stored(self):
        share, token = self.sharing.create_share(
            self.owner,
            CollaborationResourceType.TASK,
            self.task.id,
            CollaborationRole.EDITOR,
        )
        self.assertTrue(token)
        self.assertEqual(share.token_hash, hash_secret(token))
        self.assertNotEqual(share.token_hash, token)  # never the raw token
        self.assertTrue(SharingService.is_active(share))
        self.assertEqual(share.role, CollaborationRole.EDITOR.value)

    def test_non_owner_participant_cannot_create_share(self):
        # Add the collaborator as an editor, then have them try to share.
        self._add_collaborator(CollaborationResourceType.TASK, self.task.id)
        with self.assertRaises(CollaborationAccessDeniedError):
            self.sharing.create_share(
                self.collaborator,
                CollaborationResourceType.TASK,
                self.task.id,
                CollaborationRole.VIEWER,
            )

    def test_outsider_creating_share_sees_not_found(self):
        with self.assertRaises(ResourceNotFoundError):
            self.sharing.create_share(
                self.outsider,
                CollaborationResourceType.TASK,
                self.task.id,
                CollaborationRole.VIEWER,
            )

    def test_shares_can_be_minted_for_every_resource_type(self):
        for rtype, rid in self.resources.items():
            with self.subTest(resource=rtype.value):
                share, token = self.sharing.create_share(
                    self.owner, rtype, rid, CollaborationRole.VIEWER
                )
                self.assertTrue(SharingService.is_active(share))

    # --- Listing & revoking ---------------------------------------------

    def test_list_and_revoke(self):
        rtype, rid = CollaborationResourceType.WORKFLOW, self.workflow.id
        share, _ = self.sharing.create_share(
            self.owner, rtype, rid, CollaborationRole.VIEWER
        )
        listed = self.sharing.list_shares(self.owner, rtype, rid)
        self.assertEqual([s.id for s in listed], [share.id])

        self.sharing.revoke_share(self.owner, rtype, rid, share.id)
        self.assertIsNotNone(self.sharing.shares.get_by_id(share.id).revoked_at)

    def test_revoke_unknown_share_is_not_found(self):
        with self.assertRaises(ShareNotFoundError):
            self.sharing.revoke_share(
                self.owner,
                CollaborationResourceType.TASK,
                self.task.id,
                uuid.uuid4(),
            )

    # --- Redemption ------------------------------------------------------

    def test_redeem_makes_a_participant_at_the_shared_role(self):
        rtype, rid = CollaborationResourceType.CONVERSATION, self.conversation.id
        _, token = self.sharing.create_share(
            self.owner, rtype, rid, CollaborationRole.EDITOR
        )
        participant = self.sharing.redeem(self.collaborator, token)
        self.assertEqual(participant.role, CollaborationRole.EDITOR)
        self.assertEqual(participant.user_id, self.collaborator.id)

        role, _ = self.service.get_access(self.collaborator, rtype, rid)
        self.assertEqual(role, CollaborationRole.EDITOR)

    def test_redeem_is_idempotent(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        _, token = self.sharing.create_share(
            self.owner, rtype, rid, CollaborationRole.VIEWER
        )
        first = self.sharing.redeem(self.collaborator, token)
        second = self.sharing.redeem(self.collaborator, token)
        self.assertEqual(first.id, second.id)  # same participant, no duplicate

    def test_owner_redeeming_own_link_is_a_noop(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        _, token = self.sharing.create_share(
            self.owner, rtype, rid, CollaborationRole.VIEWER
        )
        result = self.sharing.redeem(self.owner, token)
        self.assertTrue(result.is_owner)
        self.assertIsNone(result.id)

    def test_redeem_unknown_token_is_not_found(self):
        with self.assertRaises(ShareNotFoundError):
            self.sharing.redeem(self.collaborator, "nope-not-a-real-token")

    def test_redeem_revoked_link_is_inactive(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        share, token = self.sharing.create_share(
            self.owner, rtype, rid, CollaborationRole.VIEWER
        )
        self.sharing.revoke_share(self.owner, rtype, rid, share.id)
        with self.assertRaises(ShareInactiveError):
            self.sharing.redeem(self.collaborator, token)

    def test_redeem_expired_link_is_inactive(self):
        rtype, rid = CollaborationResourceType.TASK, self.task.id
        share, token = self.sharing.create_share(
            self.owner, rtype, rid, CollaborationRole.VIEWER, expires_in_days=1
        )
        # Push the expiry into the past.
        share.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        self.session.commit()
        with self.assertRaises(ShareInactiveError):
            self.sharing.redeem(self.collaborator, token)

    # --- Helper ----------------------------------------------------------

    def _add_collaborator(self, rtype, rid, role=CollaborationRole.EDITOR):
        from app.schemas.collaboration import ParticipantCreate
        from app.utils.constants import ParticipantType

        self.service.add_participant(
            self.owner,
            rtype,
            rid,
            ParticipantCreate(
                participant_type=ParticipantType.USER,
                user_id=self.collaborator.id,
                role=role,
            ),
        )


class SharingAPITests(CollaborationFixture):
    """The sharing endpoints end-to-end, over the same real session."""

    def setUp(self):
        super().setUp()
        self._current_user = self.owner
        app.dependency_overrides[get_current_user] = lambda: self._current_user
        app.dependency_overrides[get_sharing_service] = (
            lambda: SharingService(self.session)
        )
        app.dependency_overrides[get_collaboration_service] = (
            lambda: CollaborationService(self.session)
        )
        self.client = TestClient(app)

    def _shares_url(self, rtype, rid):
        return f"/api/v1/collaboration/{rtype.value}/{rid}/shares"

    def test_create_returns_token_and_path_once(self):
        resp = self.client.post(
            self._shares_url(CollaborationResourceType.TASK, self.task.id),
            json={"role": "editor"},
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertIn("token", body)
        self.assertTrue(body["token"])
        self.assertTrue(body["path"].endswith(body["token"]))
        self.assertTrue(body["is_active"])
        self.assertEqual(body["role"], "editor")

    def test_create_owner_role_is_422(self):
        resp = self.client.post(
            self._shares_url(CollaborationResourceType.TASK, self.task.id),
            json={"role": "owner"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_list_excludes_token(self):
        self.client.post(
            self._shares_url(CollaborationResourceType.TASK, self.task.id),
            json={"role": "viewer"},
        )
        resp = self.client.get(
            self._shares_url(CollaborationResourceType.TASK, self.task.id)
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("token", rows[0])

    def test_revoke_then_redeem_is_410(self):
        created = self.client.post(
            self._shares_url(CollaborationResourceType.TASK, self.task.id),
            json={"role": "viewer"},
        ).json()
        token = created["token"]
        deleted = self.client.delete(
            self._shares_url(CollaborationResourceType.TASK, self.task.id)
            + f"/{created['id']}"
        )
        self.assertEqual(deleted.status_code, 204)

        self._current_user = self.collaborator
        redeemed = self.client.post(
            "/api/v1/collaboration/shares/redeem", json={"token": token}
        )
        self.assertEqual(redeemed.status_code, 410)

    def test_redeem_makes_participant(self):
        created = self.client.post(
            self._shares_url(CollaborationResourceType.MEMORY, self.memory.id),
            json={"role": "viewer"},
        ).json()
        self._current_user = self.collaborator
        redeemed = self.client.post(
            "/api/v1/collaboration/shares/redeem", json={"token": created["token"]}
        )
        self.assertEqual(redeemed.status_code, 200)
        self.assertEqual(redeemed.json()["role"], "viewer")
        # The collaborator can now see the resource's participants.
        listed = self.client.get(
            f"/api/v1/collaboration/memory/{self.memory.id}/participants"
        )
        self.assertEqual(listed.status_code, 200)

    def test_redeem_unknown_token_is_404(self):
        self._current_user = self.collaborator
        resp = self.client.post(
            "/api/v1/collaboration/shares/redeem", json={"token": "bogus"}
        )
        self.assertEqual(resp.status_code, 404)

    def test_outsider_cannot_create_share(self):
        self._current_user = self.outsider
        resp = self.client.post(
            self._shares_url(CollaborationResourceType.TASK, self.task.id),
            json={"role": "viewer"},
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
