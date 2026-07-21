"""Sharing service: secure collaboration links (Sprint 20B).

Turns a resource into something an owner can hand to another user through a
link, without re-implementing ownership or participation. Every decision reuses
the Sprint 20A core:

* who may create, list, or revoke a share is decided by
  :class:`CollaborationService` access resolution (owner only);
* redeeming a share grants participation through
  :meth:`CollaborationService.grant_user_participation`, so a redeemer becomes a
  first-class participant governed by the same permission rules.

The link's secret is generated with :mod:`secrets` and stored only as a SHA-256
digest via the platform's existing :func:`hash_secret`; the raw token is
returned once at creation and never persisted. A link is redeemable while it is
neither revoked nor expired.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Tuple

from app.core.security import hash_secret
from app.models.collaboration_share import CollaborationShare
from app.models.user import User
from app.repositories.collaboration_share_repository import (
    CollaborationShareRepository,
)
from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.notification_emitter import NotificationEmitter
from app.services.collaboration.service import (
    CollaborationAccessDeniedError,
    CollaborationService,
    ResolvedParticipant,
)
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
    CollaborationRole,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SharingError(Exception):
    """Base class for sharing domain errors."""


class ShareNotFoundError(SharingError):
    """No such share on this resource, or the token matches nothing."""


class ShareInactiveError(SharingError):
    """The share exists but has been revoked or has expired."""


#: How many random bytes back a share token. 32 bytes of url-safe entropy is the
#: same strength the password-reset token uses.
_TOKEN_BYTES = 32


class SharingService:
    """Coordinates share links, reusing the collaboration core for every decision.

    Owns the unit of work: the repository flushes, this service commits. Holds
    no state beyond its session-bound collaborators.
    """

    def __init__(
        self,
        session,
        recorder: Optional[ActivityRecorder] = None,
        notifier: Optional[NotificationEmitter] = None,
    ) -> None:
        self.session = session
        self.shares = CollaborationShareRepository(session)
        # The composed collaboration service is intentionally recorder- and
        # notifier-free, so sharing owns its own timeline/inbox events (a
        # shared/joined story, not a duplicate participant-added one).
        self.collaboration = CollaborationService(session)
        self.recorder = recorder
        self.notifier = notifier

    # --- Owner-side management ------------------------------------------

    def create_share(
        self,
        owner: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        role: CollaborationRole,
        expires_in_days: Optional[int] = None,
    ) -> Tuple[CollaborationShare, str]:
        """Mint a share link. Owner only. Returns the row and the raw token once.

        The token is generated here, hashed for storage, and returned to the
        caller a single time — it cannot be recovered from the stored row.
        """
        self._require_owner(owner, resource_type, resource_id)

        token = secrets.token_urlsafe(_TOKEN_BYTES)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else None
        )
        share = CollaborationShare(
            resource_type=resource_type.value,
            resource_id=resource_id,
            token_hash=hash_secret(token),
            role=role.value,
            created_by_user_id=owner.id,
            expires_at=expires_at,
        )
        self.shares.add(share)
        self.session.commit()
        logger.info(
            "User %s created a %s share link for %s %s",
            owner.id,
            role.value,
            resource_type.value,
            resource_id,
        )
        self._emit(
            resource_type,
            resource_id,
            ActivityKind.SHARED,
            owner,
            f"Created a {role.value} share link",
        )
        return share, token

    def list_shares(
        self,
        owner: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
    ) -> Sequence[CollaborationShare]:
        """Every share link on the resource. Owner only."""
        self._require_owner(owner, resource_type, resource_id)
        return self.shares.list_for_resource(resource_type.value, resource_id)

    def revoke_share(
        self,
        owner: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        share_id: uuid.UUID,
    ) -> None:
        """Withdraw a share link. Owner only. Idempotent once revoked."""
        self._require_owner(owner, resource_type, resource_id)
        share = self.shares.get_by_id(share_id)
        if (
            share is None
            or share.resource_type != resource_type.value
            or share.resource_id != resource_id
        ):
            raise ShareNotFoundError(str(share_id))
        if share.revoked_at is None:
            share.revoked_at = datetime.now(timezone.utc)
            self.session.commit()
            self._emit(
                resource_type,
                resource_id,
                ActivityKind.SHARE_REVOKED,
                owner,
                "Revoked a share link",
            )

    # --- Redemption ------------------------------------------------------

    def redeem(self, user: User, token: str) -> ResolvedParticipant:
        """Join a resource by presenting a share token.

        A missing token reads as not found; a revoked or expired one reads as
        inactive — the redeemer benefits from knowing which. On success the user
        becomes a participant at the share's role, through the collaboration core.
        """
        share = self.shares.get_by_token_hash(hash_secret(token))
        if share is None:
            raise ShareNotFoundError("token")
        if not share.is_active(datetime.now(timezone.utc)):
            raise ShareInactiveError("token")
        resource_type = CollaborationResourceType(share.resource_type)
        granted = self.collaboration.grant_user_participation(
            resource_type,
            share.resource_id,
            user,
            CollaborationRole(share.role),
            added_by_user_id=share.created_by_user_id,
        )
        # Only a genuine join (not the owner redeeming their own link) is an event.
        if not granted.is_owner:
            self._emit(
                resource_type,
                share.resource_id,
                ActivityKind.JOINED,
                user,
                f"Joined as {granted.role.value} via a share link",
            )
            self._notify_owner_of_join(resource_type, share.resource_id, user, granted)
        return granted

    # --- Helpers ---------------------------------------------------------

    def _require_owner(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
    ) -> None:
        """Only the resource owner manages its share links.

        Access is resolved by the collaboration core: a non-participant already
        gets not-found (existence stays hidden); a participant who is not the
        owner is refused here.
        """
        _, is_owner = self.collaboration.get_access(
            user, resource_type, resource_id
        )
        if not is_owner:
            raise CollaborationAccessDeniedError("only the owner may manage shares")

    def _emit(
        self,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        kind: ActivityKind,
        actor: User,
        summary: str,
    ) -> None:
        """Record a timeline event when a recorder is attached (best-effort)."""
        if self.recorder is None:
            return
        self.recorder.record(
            resource_type,
            resource_id,
            kind,
            summary,
            actor_type=ActivityActorType.USER,
            actor_id=actor.id,
        )

    def _notify_owner_of_join(
        self,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        joiner: User,
        granted: ResolvedParticipant,
    ) -> None:
        """Tell the resource owner that someone joined through their link."""
        if self.notifier is None:
            return
        ref = self.collaboration.resolver.load(resource_type, resource_id)
        if ref is None:
            return
        joiner_name = joiner.full_name or joiner.email
        self.notifier.emit(
            ref.owner_user_id,
            NotificationEmitter.type_for(resource_type),
            f"{joiner_name} joined your {resource_type.value}",
            f"They joined as {granted.role.value} via a share link.",
            resource_type=resource_type,
            resource_id=resource_id,
            actor_type=ActivityActorType.USER,
            actor_id=joiner.id,
        )

    @staticmethod
    def is_active(share: CollaborationShare) -> bool:
        """Whether a share is currently redeemable — for building responses."""
        return share.is_active(datetime.now(timezone.utc))
