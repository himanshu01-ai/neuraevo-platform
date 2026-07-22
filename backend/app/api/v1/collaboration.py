"""Collaboration Platform API — participants & access (Sprint 20, slice 20A).

One participant surface for every collaborated resource. The path names the
resource polymorphically — ``/collaboration/{resource_type}/{resource_id}/…`` —
so a conversation, task, workflow, or memory is shared through the *same*
endpoints, and a future resource type joins without a new route. Ownership and
access are decided in :class:`CollaborationService`; this layer only validates
the request, injects the service, and translates domain errors to HTTP.

Additive and backwards compatible: no existing route changes, and the four
owning domains keep their own APIs untouched.
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Response, status

from app.core.dependencies import (
    ActivityServiceDep,
    CollaborationServiceDep,
    CurrentUserDep,
    NotificationServiceDep,
    SharingServiceDep,
)
from app.schemas.collaboration import (
    AccessResponse,
    ActivityEventResponse,
    NotificationCountsResponse,
    NotificationResponse,
    NotificationUpdate,
    ParticipantCreate,
    ParticipantResponse,
    ParticipantRoleUpdate,
    ShareCreate,
    ShareCreatedResponse,
    ShareRedeemRequest,
    ShareResponse,
)
from app.services.collaboration.activity_service import (
    ActivityScope,
    ResolvedActivity,
)
from app.services.collaboration.notification_service import (
    NotificationNotFoundError,
    ResolvedNotification,
)
from app.services.collaboration.service import (
    CollaborationAccessDeniedError,
    CollaborationValidationError,
    DuplicateParticipantError,
    ParticipantNotFoundError,
    ResolvedParticipant,
    ResourceNotFoundError,
)
from app.services.collaboration.sharing_service import (
    ShareInactiveError,
    ShareNotFoundError,
    SharingService,
)
from app.models.collaboration_share import CollaborationShare
from app.utils.constants import CollaborationResourceType

#: Relative frontend route a recipient opens to redeem a share token. Kept here
#: so the token-to-link mapping lives in one place.
_SHARE_PATH = "/collaboration/join/{token}"

router = APIRouter(prefix="/collaboration", tags=["Collaboration"])

_ACCESS_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {
        "description": "You can see this resource but lack the role for this action."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The resource does not exist, or you are not a participant."
    },
}


def _to_http_exception(exc: Exception) -> HTTPException:
    """Translate a collaboration domain error into its HTTP equivalent."""
    if isinstance(
        exc,
        (
            ResourceNotFoundError,
            ParticipantNotFoundError,
            ShareNotFoundError,
            NotificationNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc) or "Not found."
        )
    if isinstance(exc, ShareInactiveError):
        return HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has expired or been revoked.",
        )
    if isinstance(exc, CollaborationAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this resource.",
        )
    if isinstance(exc, DuplicateParticipantError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, CollaborationValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        )
    raise exc


def _share_response(share: CollaborationShare) -> ShareResponse:
    """Map a share row to the owner's management view (never the token)."""
    return ShareResponse(
        id=share.id,
        resource_type=CollaborationResourceType(share.resource_type),
        resource_id=share.resource_id,
        role=share.role,
        created_by_user_id=share.created_by_user_id,
        is_active=SharingService.is_active(share),
        expires_at=share.expires_at,
        revoked_at=share.revoked_at,
        created_at=share.created_at,
    )


def _to_response(participant: ResolvedParticipant) -> ParticipantResponse:
    """Map the service's resolved participant to the wire shape."""
    return ParticipantResponse(
        id=participant.id,
        resource_type=participant.resource_type,
        resource_id=participant.resource_id,
        participant_type=participant.participant_type,
        role=participant.role,
        is_owner=participant.is_owner,
        user_id=participant.user_id,
        employee_id=participant.employee_id,
        name=participant.name,
        created_at=participant.created_at,
    )


@router.get(
    "/{resource_type}/{resource_id}/access",
    response_model=AccessResponse,
    summary="Your effective role on a resource",
    responses=_ACCESS_RESPONSES,
)
def get_access(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: CollaborationServiceDep,
) -> AccessResponse:
    """Return the authenticated user's role on the resource, and if they own it.

    The frontend gates its controls from this — a viewer never sees an *Add
    participant* button — without re-deriving the permission rules.
    """
    try:
        role, is_owner = service.get_access(current_user, resource_type, resource_id)
    except (ResourceNotFoundError, CollaborationAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return AccessResponse(
        resource_type=resource_type,
        resource_id=resource_id,
        role=role,
        is_owner=is_owner,
    )


@router.get(
    "/{resource_type}/{resource_id}/participants",
    response_model=List[ParticipantResponse],
    summary="List a resource's participants",
    responses=_ACCESS_RESPONSES,
)
def list_participants(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: CollaborationServiceDep,
) -> List[ParticipantResponse]:
    """Everyone on the resource — the owner first, then invited collaborators.

    Any participant may read this; a non-participant gets 404 so a resource's
    existence is never revealed to someone without access.
    """
    try:
        participants = service.list_participants(
            current_user, resource_type, resource_id
        )
    except (ResourceNotFoundError, CollaborationAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return [_to_response(p) for p in participants]


@router.post(
    "/{resource_type}/{resource_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a participant to a resource",
    responses={
        **_ACCESS_RESPONSES,
        status.HTTP_409_CONFLICT: {
            "description": "That user or employee is already a participant."
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The payload references an unknown user or an employee that isn't yours."
        },
    },
)
def add_participant(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    data: ParticipantCreate,
    current_user: CurrentUserDep,
    service: CollaborationServiceDep,
) -> ParticipantResponse:
    """Invite a user or an AI employee onto the resource. Owner only.

    An AI employee joins on the same footing as a person — the participant model
    is not user-only. The owner is taken from the bearer token, never the payload.
    """
    try:
        participant = service.add_participant(
            current_user, resource_type, resource_id, data
        )
    except (
        ResourceNotFoundError,
        CollaborationAccessDeniedError,
        DuplicateParticipantError,
        CollaborationValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(participant)


@router.patch(
    "/{resource_type}/{resource_id}/participants/{participant_id}",
    response_model=ParticipantResponse,
    summary="Change a participant's role",
    responses=_ACCESS_RESPONSES,
)
def update_participant_role(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    participant_id: uuid.UUID,
    data: ParticipantRoleUpdate,
    current_user: CurrentUserDep,
    service: CollaborationServiceDep,
) -> ParticipantResponse:
    """Re-role a participant (editor ↔ viewer). Owner only.

    Ownership is not assignable here — the schema rejects ``owner`` — so this
    never changes who owns the resource.
    """
    try:
        participant = service.update_participant_role(
            current_user, resource_type, resource_id, participant_id, data.role
        )
    except (
        ResourceNotFoundError,
        ParticipantNotFoundError,
        CollaborationAccessDeniedError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(participant)


@router.delete(
    "/{resource_type}/{resource_id}/participants/{participant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a participant from a resource",
    responses=_ACCESS_RESPONSES,
)
def remove_participant(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    participant_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: CollaborationServiceDep,
) -> Response:
    """Remove a participant. Owner only. Removing the owner is impossible —
    they have no participant row to remove."""
    try:
        service.remove_participant(
            current_user, resource_type, resource_id, participant_id
        )
    except (
        ResourceNotFoundError,
        ParticipantNotFoundError,
        CollaborationAccessDeniedError,
    ) as exc:
        raise _to_http_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =====================================================================
# Sharing (Sprint 20B) — secure collaboration links
# =====================================================================


@router.post(
    "/{resource_type}/{resource_id}/shares",
    response_model=ShareCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a secure share link for a resource",
    responses=_ACCESS_RESPONSES,
)
def create_share(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    data: ShareCreate,
    current_user: CurrentUserDep,
    service: SharingServiceDep,
) -> ShareCreatedResponse:
    """Mint a share link granting the chosen role. Owner only.

    The raw token is returned exactly once, in this response — it cannot be
    recovered from the stored row later. ``path`` is the relative route a
    recipient opens to redeem it.
    """
    try:
        share, token = service.create_share(
            current_user,
            resource_type,
            resource_id,
            data.role,
            data.expires_in_days,
        )
    except (ResourceNotFoundError, CollaborationAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    base = _share_response(share)
    return ShareCreatedResponse(
        **base.model_dump(),
        token=token,
        path=_SHARE_PATH.format(token=token),
    )


@router.get(
    "/{resource_type}/{resource_id}/shares",
    response_model=List[ShareResponse],
    summary="List a resource's share links",
    responses=_ACCESS_RESPONSES,
)
def list_shares(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: SharingServiceDep,
) -> List[ShareResponse]:
    """Every share link on the resource, newest first. Owner only.

    Tokens are never included — only the links' roles, expiry, and whether each
    is still redeemable.
    """
    try:
        shares = service.list_shares(current_user, resource_type, resource_id)
    except (ResourceNotFoundError, CollaborationAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return [_share_response(s) for s in shares]


@router.delete(
    "/{resource_type}/{resource_id}/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share link",
    responses=_ACCESS_RESPONSES,
)
def revoke_share(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    share_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: SharingServiceDep,
) -> Response:
    """Withdraw a share link so it can no longer be redeemed. Owner only.

    Existing participants who joined through it keep their access — revoking a
    link closes the door, it does not evict who already walked through.
    """
    try:
        service.revoke_share(current_user, resource_type, resource_id, share_id)
    except (
        ResourceNotFoundError,
        ShareNotFoundError,
        CollaborationAccessDeniedError,
    ) as exc:
        raise _to_http_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/shares/redeem",
    response_model=ParticipantResponse,
    summary="Redeem a share token to join its resource",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No share matches this token."},
        status.HTTP_410_GONE: {
            "description": "The share link has expired or been revoked."
        },
    },
)
def redeem_share(
    data: ShareRedeemRequest,
    current_user: CurrentUserDep,
    service: SharingServiceDep,
) -> ParticipantResponse:
    """Join a resource by presenting a share token.

    The authenticated user becomes a participant at the link's role, through the
    same participation rules the owner-driven path uses. Redeeming a link one
    already holds is idempotent.
    """
    try:
        participant = service.redeem(current_user, data.token)
    except (ShareNotFoundError, ShareInactiveError) as exc:
        raise _to_http_exception(exc)
    return _to_response(participant)


# =====================================================================
# Activity timeline (Sprint 20C)
# =====================================================================


def _activity_response(event: ResolvedActivity) -> ActivityEventResponse:
    """Map the service's resolved event to the wire shape."""
    return ActivityEventResponse(
        id=event.id,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        kind=event.kind,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        actor_name=event.actor_name,
        summary=event.summary,
        is_own=event.is_own,
        created_at=event.created_at,
    )


@router.get(
    "/activity",
    response_model=List[ActivityEventResponse],
    summary="The authenticated user's activity feed",
)
def list_activity_feed(
    current_user: CurrentUserDep,
    service: ActivityServiceDep,
    scope: ActivityScope = ActivityScope.ALL,
    limit: int = 50,
) -> List[ActivityEventResponse]:
    """Activity across every resource the user owns or participates in.

    ``scope=all`` is the team feed; ``mine`` is what the user did; ``mentions``
    is the subset that tags them. Newest first.
    """
    events = service.list_for_user(current_user, scope=scope, limit=limit)
    return [_activity_response(e) for e in events]


@router.get(
    "/{resource_type}/{resource_id}/activity",
    response_model=List[ActivityEventResponse],
    summary="One resource's activity timeline",
    responses=_ACCESS_RESPONSES,
)
def list_resource_activity(
    resource_type: CollaborationResourceType,
    resource_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ActivityServiceDep,
    limit: int = 50,
) -> List[ActivityEventResponse]:
    """A single resource's timeline, newest first. Any participant may read it."""
    try:
        events = service.list_for_resource(
            current_user, resource_type, resource_id, limit=limit
        )
    except (ResourceNotFoundError, CollaborationAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return [_activity_response(e) for e in events]


# =====================================================================
# Notifications (Sprint 20D) — the collaboration inbox
# =====================================================================


def _notification_response(
    notification: ResolvedNotification,
) -> NotificationResponse:
    """Map the service's resolved notification to the wire shape."""
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        description=notification.description,
        resource_type=notification.resource_type,
        resource_id=notification.resource_id,
        actor_type=notification.actor_type,
        actor_id=notification.actor_id,
        actor_name=notification.actor_name,
        priority=notification.priority,
        read=notification.read,
        archived=notification.archived,
        pinned=notification.pinned,
        bookmarked=notification.bookmarked,
        following=notification.following,
        muted=notification.muted,
        created_at=notification.created_at,
    )


@router.get(
    "/notifications",
    response_model=List[NotificationResponse],
    summary="The authenticated user's notifications",
)
def list_notifications(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
    include_archived: bool = False,
    limit: int = 50,
) -> List[NotificationResponse]:
    """The user's inbox, newest first. Archived items are excluded by default."""
    rows = service.list_for_user(
        current_user, include_archived=include_archived, limit=limit
    )
    return [_notification_response(n) for n in rows]


@router.get(
    "/notifications/counts",
    response_model=NotificationCountsResponse,
    summary="Notification badge counts",
)
def notification_counts(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> NotificationCountsResponse:
    """The tallies the header and nav badges show."""
    counts = service.counts(current_user)
    return NotificationCountsResponse(
        unread=counts.unread,
        mentions=counts.mentions,
        pending_approvals=counts.pending_approvals,
        bookmarked=counts.bookmarked,
    )


@router.post(
    "/notifications/read-all",
    response_model=List[NotificationResponse],
    summary="Mark every unread notification read",
)
def mark_all_read(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> List[NotificationResponse]:
    """Clear the unread state across the inbox, returning it as it now stands."""
    rows = service.mark_all_read(current_user)
    return [_notification_response(n) for n in rows]


@router.get(
    "/notifications/{notification_id}",
    response_model=NotificationResponse,
    summary="Get one notification",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No such notification."}
    },
)
def get_notification(
    notification_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> NotificationResponse:
    """One of the user's own notifications."""
    try:
        notification = service.get(current_user, notification_id)
    except NotificationNotFoundError as exc:
        raise _to_http_exception(exc)
    return _notification_response(notification)


@router.patch(
    "/notifications/{notification_id}",
    response_model=NotificationResponse,
    summary="Toggle a notification's quick-action flags",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No such notification."}
    },
)
def update_notification(
    notification_id: uuid.UUID,
    data: NotificationUpdate,
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> NotificationResponse:
    """Mark read/unread, archive, pin, bookmark, follow, or mute — any subset in
    one call. Only supplied fields change."""
    try:
        notification = service.update(current_user, notification_id, data)
    except NotificationNotFoundError as exc:
        raise _to_http_exception(exc)
    return _notification_response(notification)
