"""Pydantic schemas for the Collaboration Platform (Sprint 20).

The ORM model is never exposed; every endpoint speaks in these types. The
create payload is deliberately a discriminated shape: a participant is a user
*or* an employee, so exactly one identity may be supplied and it must match the
declared ``participant_type`` — the same rule the model's check constraint
enforces, validated here first so a bad payload is a clean 422 rather than a
database error.

``OWNER`` is never an acceptable input role. Ownership is derived from the
resource's existing chain, not granted through this API, so the create/update
payloads reject it up front.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
    CollaborationRole,
    EmployeePriority,
    NotificationType,
    ParticipantType,
)


def _reject_owner(role: CollaborationRole) -> CollaborationRole:
    """Guard shared by create and update: ownership is never assignable here."""
    if role is CollaborationRole.OWNER:
        raise ValueError(
            "owner is derived from the resource, not granted; choose editor or viewer"
        )
    return role


class ParticipantCreate(BaseModel):
    """Add a collaborator to a resource.

    Supply ``user_id`` for a person or ``employee_id`` for an AI employee — one,
    never both, matching ``participant_type``. ``role`` is ``editor`` or
    ``viewer``; ``owner`` is rejected.
    """

    participant_type: ParticipantType
    role: CollaborationRole = CollaborationRole.VIEWER
    user_id: Optional[uuid.UUID] = None
    employee_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def _check_identity(self) -> "ParticipantCreate":
        _reject_owner(self.role)
        if self.participant_type is ParticipantType.USER:
            if self.user_id is None or self.employee_id is not None:
                raise ValueError("a user participant requires user_id and no employee_id")
        else:  # EMPLOYEE
            if self.employee_id is None or self.user_id is not None:
                raise ValueError(
                    "an employee participant requires employee_id and no user_id"
                )
        return self


class ParticipantRoleUpdate(BaseModel):
    """Change a participant's role. ``owner`` is rejected, as on create."""

    role: CollaborationRole

    @model_validator(mode="after")
    def _check_role(self) -> "ParticipantRoleUpdate":
        _reject_owner(self.role)
        return self


class ParticipantResponse(BaseModel):
    """One participant as the UI shows it.

    Identity plus a resolved display ``name`` — the reference-only rule the rest
    of the platform follows, so the owning module still owns the full record.
    ``is_owner`` marks the synthetic owner entry, which has no participant row of
    its own (``id`` is null for it) because ownership lives in the resource's own
    chain.
    """

    model_config = ConfigDict(from_attributes=True)

    id: Optional[uuid.UUID]
    resource_type: CollaborationResourceType
    resource_id: uuid.UUID
    participant_type: ParticipantType
    role: CollaborationRole
    is_owner: bool
    user_id: Optional[uuid.UUID]
    employee_id: Optional[uuid.UUID]
    name: str
    created_at: Optional[datetime]


class AccessResponse(BaseModel):
    """The authenticated user's effective role on a resource.

    Lets the frontend gate controls (hide *Add participant* for a viewer)
    without duplicating the permission rules — the server states the role and
    whether the caller is the owner.
    """

    resource_type: CollaborationResourceType
    resource_id: uuid.UUID
    role: CollaborationRole
    is_owner: bool


# =====================================================================
# Sharing (Sprint 20B)
# =====================================================================


class ShareCreate(BaseModel):
    """Mint a share link. ``role`` is the role a redeemer is granted.

    ``owner`` is rejected — a link grants collaboration, never ownership.
    ``expires_in_days`` bounds the link's life; omit it for a link that never
    expires.
    """

    role: CollaborationRole = CollaborationRole.VIEWER
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def _check_role(self) -> "ShareCreate":
        _reject_owner(self.role)
        return self


class ShareResponse(BaseModel):
    """A share link as the owner's management view shows it.

    The token is never here — only the fact of the link, its granted role, and
    whether it is still redeemable.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_type: CollaborationResourceType
    resource_id: uuid.UUID
    role: CollaborationRole
    created_by_user_id: uuid.UUID
    is_active: bool
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime


class ShareCreatedResponse(ShareResponse):
    """The one-time creation response — the only place the raw token appears.

    ``token`` cannot be recovered from the stored row afterward; ``path`` is the
    relative frontend route a recipient opens to redeem it.
    """

    token: str
    path: str


class ShareRedeemRequest(BaseModel):
    """Redeem a share token to join its resource."""

    token: str = Field(min_length=1)


# =====================================================================
# Activity timeline (Sprint 20C)
# =====================================================================


class ActivityEventResponse(BaseModel):
    """One timeline event as the UI shows it.

    Identity plus a resolved actor ``name`` — the reference-only rule, so the
    owning module still owns the full record. ``is_own`` marks events the caller
    themselves caused, powering the personal Activity feed.
    """

    id: uuid.UUID
    resource_type: CollaborationResourceType
    resource_id: uuid.UUID
    kind: ActivityKind
    actor_type: ActivityActorType
    actor_id: Optional[uuid.UUID]
    actor_name: str
    summary: str
    is_own: bool
    created_at: datetime


# =====================================================================
# Notifications (Sprint 20D)
# =====================================================================


class NotificationResponse(BaseModel):
    """One notification as the inbox shows it.

    Carries the quick-action flags the notification center toggles and a
    resolved actor ``name`` (reference-only — the owning module owns the rest).
    """

    id: uuid.UUID
    type: NotificationType
    title: str
    description: str
    resource_type: Optional[CollaborationResourceType]
    resource_id: Optional[uuid.UUID]
    actor_type: Optional[ActivityActorType]
    actor_id: Optional[uuid.UUID]
    actor_name: Optional[str]
    priority: EmployeePriority
    read: bool
    archived: bool
    pinned: bool
    bookmarked: bool
    following: bool
    muted: bool
    created_at: datetime


class NotificationUpdate(BaseModel):
    """Toggle any subset of a notification's quick-action flags.

    Only supplied fields change; the service reads ``model_fields_set`` so
    omitting a field leaves it alone. This one payload backs every toggle the
    frontend offers (mark read, archive, pin, bookmark, follow, mute).
    """

    read: Optional[bool] = None
    archived: Optional[bool] = None
    pinned: Optional[bool] = None
    bookmarked: Optional[bool] = None
    following: Optional[bool] = None
    muted: Optional[bool] = None


class NotificationCountsResponse(BaseModel):
    """The tallies the header and nav badges show, carried from the platform."""

    unread: int
    mentions: int
    pending_approvals: int
    bookmarked: int
