"""Collaboration service: the platform's participant & access decisions (Sprint 20).

Sits between the API layer and the participant repository and owns every
collaboration decision: whether a resource exists, what role a caller holds on
it, and who may add, re-role, or remove a participant. Ownership is *reused*,
never re-implemented — the resource's owner comes from its own chain via
:class:`~app.services.collaboration.resources.ResourceResolver`, and an AI
employee participant is validated through :class:`EmployeeService`, the same
call every other domain uses to answer "is this employee yours?".

The effective-role rule is one place, here:

* the resource owner is always ``OWNER`` (derived, never stored);
* anyone with a participant row holds that row's role (``EDITOR``/``VIEWER``);
* everyone else has no access, and a resource they cannot see reads as *not
  found* so the API never reveals another user's resources.

This slice manages *human and employee participants*; secure share links,
activity, and notifications are later slices that build on this same core.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from app.models.collaboration_participant import CollaborationParticipant
from app.models.user import User
from app.repositories.collaboration_participant_repository import (
    CollaborationParticipantRepository,
)
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.user_repository import UserRepository
from app.schemas.collaboration import ParticipantCreate
from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.notification_emitter import NotificationEmitter
from app.services.collaboration.resources import ResourceRef, ResourceResolver
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
    EmployeeService,
)
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
    CollaborationRole,
    ParticipantType,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


# --- Errors --------------------------------------------------------------


class CollaborationError(Exception):
    """Base class for collaboration domain errors."""


class ResourceNotFoundError(CollaborationError):
    """The resource does not exist, or the caller may not see it.

    The two read the same on purpose: revealing that a resource exists to a user
    with no access would leak another user's data, so a missing resource and a
    forbidden one both surface as not found.
    """


class CollaborationAccessDeniedError(CollaborationError):
    """The caller can see the resource but lacks the role for this action."""


class ParticipantNotFoundError(CollaborationError):
    """No such participant on this resource."""


class CollaborationValidationError(CollaborationError):
    """The request references something invalid (unknown user, not-your employee)."""


class DuplicateParticipantError(CollaborationError):
    """The user or employee is already a participant of this resource."""


# --- Effective-role ordering --------------------------------------------

#: Authority order. A caller satisfies a minimum role when their rank is at
#: least the minimum's. Owner outranks editor outranks viewer.
_ROLE_RANK = {
    CollaborationRole.VIEWER: 0,
    CollaborationRole.EDITOR: 1,
    CollaborationRole.OWNER: 2,
}


@dataclass(frozen=True)
class ResolvedParticipant:
    """A participant with its display name resolved — the router's input shape.

    ``id`` and ``created_at`` are ``None`` for the synthetic owner entry, which
    has no participant row because ownership lives in the resource's own chain.
    """

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


class CollaborationService:
    """Coordinates participants and access using the reused ownership chains.

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
        self.participants = CollaborationParticipantRepository(session)
        self.resolver = ResourceResolver(session)
        self.users = UserRepository(session)
        self.employee_service = EmployeeService(session)
        self.employees_repo = EmployeeRepository(session)
        #: Optional activity emission. Injected by the DI factory so the API
        #: path records a timeline; left ``None`` when the service is composed
        #: inside another service, so events are emitted once, by the owner.
        self.recorder = recorder
        #: Optional inbox emission, same injection story as the recorder.
        self.notifier = notifier

    # --- Access resolution ----------------------------------------------

    def _load_ref(
        self, resource_type: CollaborationResourceType, resource_id: uuid.UUID
    ) -> ResourceRef:
        ref = self.resolver.load(resource_type, resource_id)
        if ref is None:
            raise ResourceNotFoundError(f"{resource_type}:{resource_id}")
        return ref

    def _role_for(
        self, user: User, ref: ResourceRef
    ) -> Optional[CollaborationRole]:
        """The user's effective role on an already-loaded resource, or None."""
        if ref.owner_user_id == user.id:
            return CollaborationRole.OWNER
        row = self.participants.get_user_participant(
            ref.resource_type.value, ref.resource_id, user.id
        )
        if row is not None:
            return CollaborationRole(row.role)
        return None

    def _require(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        minimum: CollaborationRole,
    ) -> Tuple[ResourceRef, CollaborationRole]:
        """Resolve the resource and enforce a minimum role.

        A caller with no access gets not-found (existence stays hidden); a
        caller who can see it but lacks the role gets access-denied.
        """
        ref = self._load_ref(resource_type, resource_id)
        role = self._role_for(user, ref)
        if role is None:
            raise ResourceNotFoundError(f"{resource_type}:{resource_id}")
        if _ROLE_RANK[role] < _ROLE_RANK[minimum]:
            raise CollaborationAccessDeniedError(
                f"{minimum.value} required; caller is {role.value}"
            )
        return ref, role

    def get_access(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
    ) -> Tuple[CollaborationRole, bool]:
        """The caller's effective role and whether they are the owner.

        Any participant may ask; a non-participant gets not-found.
        """
        _, role = self._require(user, resource_type, resource_id, CollaborationRole.VIEWER)
        return role, role is CollaborationRole.OWNER

    # --- Listing ---------------------------------------------------------

    def list_participants(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
    ) -> List[ResolvedParticipant]:
        """Everyone on the resource: the owner first, then invited participants.

        Any participant (viewer and up) may see who else is here.
        """
        ref, _ = self._require(
            user, resource_type, resource_id, CollaborationRole.VIEWER
        )
        rows = self.participants.list_for_resource(
            resource_type.value, resource_id
        )
        # Batch-load every name once: the owner plus each participant, keyed by
        # type. Two queries at most instead of one lookup per row (an N+1) — the
        # resolved output is identical to resolving each row on its own.
        user_ids = {ref.owner_user_id} | {
            row.user_id
            for row in rows
            if row.participant_type == ParticipantType.USER.value
            and row.user_id is not None
        }
        employee_ids = {
            row.employee_id
            for row in rows
            if row.participant_type == ParticipantType.EMPLOYEE.value
            and row.employee_id is not None
        }
        users = self.users.get_by_ids(user_ids)
        employees = self.employees_repo.get_by_ids(
            employee_ids, include_deleted=True
        )
        result: List[ResolvedParticipant] = [
            self._owner_entry(ref, users)
        ]
        for row in rows:
            result.append(self._resolve_row(ref, row, users, employees))
        return result

    # --- Mutations (owner only in this slice) ---------------------------

    def add_participant(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        data: ParticipantCreate,
    ) -> ResolvedParticipant:
        """Invite a user or an AI employee onto the resource.

        Only the owner may invite. A user must exist and be active and cannot be
        the owner (who is already implied); an employee must belong to the owner,
        validated through :class:`EmployeeService`. Either may join at most once.
        """
        ref, _ = self._require(
            user, resource_type, resource_id, CollaborationRole.OWNER
        )

        if data.participant_type is ParticipantType.USER:
            participant = self._build_user_participant(user, ref, data)
        else:
            participant = self._build_employee_participant(user, ref, data)

        self.participants.add(participant)
        self.session.commit()
        logger.info(
            "User %s added %s participant to %s %s",
            user.id,
            data.participant_type.value,
            resource_type.value,
            resource_id,
        )
        resolved = self._resolve_row(ref, participant)
        self._emit(
            ref,
            ActivityKind.PARTICIPANT_ADDED,
            user,
            f"Added {resolved.name} as {resolved.role.value}",
        )
        if participant.participant_type == ParticipantType.USER.value:
            self._notify(
                participant.user_id,
                ref,
                user,
                f"You were added to a {ref.resource_type.value}",
                f"You now have {resolved.role.value} access.",
            )
        return resolved

    def grant_user_participation(
        self,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        target_user: User,
        role: CollaborationRole,
        added_by_user_id: uuid.UUID,
    ) -> ResolvedParticipant:
        """Add a user as a participant *without* an owner-access check.

        This is the redemption path for a share link: the share is itself the
        owner's authorization, granted when they created it, so the redeemer need
        not be the owner. Participant creation still runs through this one place,
        so the same rules hold — the owner is never added as a participant, and
        redeeming a link one already holds is idempotent rather than a duplicate.
        """
        ref = self._load_ref(resource_type, resource_id)
        if target_user.id == ref.owner_user_id:
            # The owner redeeming their own link needs nothing added.
            return self._owner_entry(ref)
        existing = self.participants.get_user_participant(
            ref.resource_type.value, ref.resource_id, target_user.id
        )
        if existing is not None:
            return self._resolve_row(ref, existing)
        participant = CollaborationParticipant(
            resource_type=ref.resource_type.value,
            resource_id=ref.resource_id,
            participant_type=ParticipantType.USER.value,
            user_id=target_user.id,
            role=role.value,
            added_by_user_id=added_by_user_id,
        )
        self.participants.add(participant)
        self.session.commit()
        logger.info(
            "User %s joined %s %s by share link",
            target_user.id,
            resource_type.value,
            resource_id,
        )
        return self._resolve_row(ref, participant)

    def update_participant_role(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        participant_id: uuid.UUID,
        role: CollaborationRole,
    ) -> ResolvedParticipant:
        """Change a participant's role. Owner only."""
        ref, _ = self._require(
            user, resource_type, resource_id, CollaborationRole.OWNER
        )
        participant = self._require_participant(ref, participant_id)
        participant.role = role.value
        self.session.commit()
        resolved = self._resolve_row(ref, participant)
        self._emit(
            ref,
            ActivityKind.ROLE_CHANGED,
            user,
            f"Changed {resolved.name}'s role to {resolved.role.value}",
        )
        if participant.participant_type == ParticipantType.USER.value:
            self._notify(
                participant.user_id,
                ref,
                user,
                f"Your role changed on a {ref.resource_type.value}",
                f"You now have {resolved.role.value} access.",
            )
        return resolved

    def remove_participant(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> None:
        """Remove a participant from the resource. Owner only."""
        ref, _ = self._require(
            user, resource_type, resource_id, CollaborationRole.OWNER
        )
        participant = self._require_participant(ref, participant_id)
        removed = self._resolve_row(ref, participant)
        self.participants.delete(participant)
        self.session.commit()
        self._emit(
            ref,
            ActivityKind.PARTICIPANT_REMOVED,
            user,
            f"Removed {removed.name}",
        )

    # --- Builders & resolution ------------------------------------------

    def _build_user_participant(
        self, owner: User, ref: ResourceRef, data: ParticipantCreate
    ) -> CollaborationParticipant:
        target = self.users.get_by_id(data.user_id)  # type: ignore[arg-type]
        if target is None or not target.is_active:
            raise CollaborationValidationError("no such user")
        if target.id == ref.owner_user_id:
            raise CollaborationValidationError(
                "the owner is already a participant of this resource"
            )
        if self.participants.get_user_participant(
            ref.resource_type.value, ref.resource_id, target.id
        ) is not None:
            raise DuplicateParticipantError("user is already a participant")
        return CollaborationParticipant(
            resource_type=ref.resource_type.value,
            resource_id=ref.resource_id,
            participant_type=ParticipantType.USER.value,
            user_id=target.id,
            role=data.role.value,
            added_by_user_id=owner.id,
        )

    def _build_employee_participant(
        self, owner: User, ref: ResourceRef, data: ParticipantCreate
    ) -> CollaborationParticipant:
        try:
            # Reused ownership: the employee must belong to the resource owner,
            # who is the acting user here (OWNER was required above).
            employee = self.employee_service.get_employee(owner, data.employee_id)  # type: ignore[arg-type]
        except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
            raise CollaborationValidationError("no such employee") from exc
        if self.participants.get_employee_participant(
            ref.resource_type.value, ref.resource_id, employee.id
        ) is not None:
            raise DuplicateParticipantError("employee is already a participant")
        return CollaborationParticipant(
            resource_type=ref.resource_type.value,
            resource_id=ref.resource_id,
            participant_type=ParticipantType.EMPLOYEE.value,
            employee_id=employee.id,
            role=data.role.value,
            added_by_user_id=owner.id,
        )

    def _emit(
        self,
        ref: ResourceRef,
        kind: ActivityKind,
        actor: User,
        summary: str,
    ) -> None:
        """Record a timeline event when a recorder is attached (best-effort)."""
        if self.recorder is None:
            return
        self.recorder.record(
            ref.resource_type,
            ref.resource_id,
            kind,
            summary,
            actor_type=ActivityActorType.USER,
            actor_id=actor.id,
            owner_user_id=ref.owner_user_id,
        )

    def _notify(
        self,
        recipient_user_id: uuid.UUID,
        ref: ResourceRef,
        actor: User,
        title: str,
        description: str,
    ) -> None:
        """Raise an inbox notification when a notifier is attached (best-effort)."""
        if self.notifier is None:
            return
        self.notifier.emit(
            recipient_user_id,
            NotificationEmitter.type_for(ref.resource_type),
            title,
            description,
            resource_type=ref.resource_type,
            resource_id=ref.resource_id,
            actor_type=ActivityActorType.USER,
            actor_id=actor.id,
        )

    def _require_participant(
        self, ref: ResourceRef, participant_id: uuid.UUID
    ) -> CollaborationParticipant:
        participant = self.participants.get_by_id(participant_id)
        if (
            participant is None
            or participant.resource_type != ref.resource_type.value
            or participant.resource_id != ref.resource_id
        ):
            raise ParticipantNotFoundError(str(participant_id))
        return participant

    def _owner_entry(
        self, ref: ResourceRef, users: Optional[dict] = None
    ) -> ResolvedParticipant:
        return ResolvedParticipant(
            id=None,
            resource_type=ref.resource_type,
            resource_id=ref.resource_id,
            participant_type=ParticipantType.USER,
            role=CollaborationRole.OWNER,
            is_owner=True,
            user_id=ref.owner_user_id,
            employee_id=None,
            name=self._user_name(ref.owner_user_id, users),
            created_at=None,
        )

    def _resolve_row(
        self,
        ref: ResourceRef,
        row: CollaborationParticipant,
        users: Optional[dict] = None,
        employees: Optional[dict] = None,
    ) -> ResolvedParticipant:
        is_user = row.participant_type == ParticipantType.USER.value
        name = (
            self._user_name(row.user_id, users)
            if is_user
            else self._employee_name(row.employee_id, employees)
        )
        return ResolvedParticipant(
            id=row.id,
            resource_type=ref.resource_type,
            resource_id=ref.resource_id,
            participant_type=ParticipantType(row.participant_type),
            role=CollaborationRole(row.role),
            is_owner=False,
            user_id=row.user_id,
            employee_id=row.employee_id,
            name=name,
            created_at=row.created_at,
        )

    def _user_name(
        self, user_id: Optional[uuid.UUID], users: Optional[dict] = None
    ) -> str:
        """A user's display name; reads a prefetched ``users`` map when the
        batched list path supplies one, else falls back to a single fetch."""
        if user_id is None:
            return "Unknown user"
        user = (
            users.get(user_id)
            if users is not None
            else self.users.get_by_id(user_id)
        )
        if user is None:
            return "Unknown user"
        return user.full_name or user.email

    def _employee_name(
        self, employee_id: Optional[uuid.UUID], employees: Optional[dict] = None
    ) -> str:
        """An employee's display name; reads a prefetched ``employees`` map when
        the batched list path supplies one, else falls back to a single fetch."""
        if employee_id is None:
            return "AI employee"
        employee = (
            employees.get(employee_id)
            if employees is not None
            else self.employees_repo.get_by_id(employee_id, include_deleted=True)
        )
        return employee.name if employee is not None else "AI employee"
