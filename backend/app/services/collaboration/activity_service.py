"""Activity service: the timeline's read surface (Sprint 20C).

Reads the append-only timeline two ways, both permission-aware by reusing the
Sprint 20A core:

* a **resource timeline** — one resource's events, visible to any participant
  (viewer and up), gated by :meth:`CollaborationService.get_access`;
* a **per-user feed** — events across every resource the user owns or
  participates in, for the Activity/Team/Mentions screens. The visible set is
  the union of the user's owned resources (one indexed read on the denormalised
  ``owner_user_id``) and their participant resources (one read on the
  participant table), so no cross-domain scan is needed.

Writing is not here — that is :class:`ActivityRecorder`, which the collaboration
and sharing services hold. This service never records; it only reads and
resolves display names, following the reference-only rule the rest of the
platform uses.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from app.models.activity_event import ActivityEvent
from app.models.user import User
from app.repositories.activity_event_repository import ActivityEventRepository
from app.repositories.collaboration_participant_repository import (
    CollaborationParticipantRepository,
)
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.user_repository import UserRepository
from app.services.collaboration.service import CollaborationService
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
)


class ActivityScope(str, Enum):
    """Which slice of the user's feed to return."""

    #: Everything on resources the user can see — the team feed.
    ALL = "all"
    #: Only what the user themselves did — the personal Activity feed.
    MINE = "mine"
    #: Only events that mention the user.
    MENTIONS = "mentions"


#: Hard ceiling on a single feed read, matching the Memory Engine's safeguard.
_MAX_LIMIT = 100


@dataclass(frozen=True)
class ResolvedActivity:
    """One timeline event with its actor's display name resolved."""

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


class ActivityService:
    """Reads the timeline, permission-aware, resolving actor names."""

    def __init__(self, session) -> None:
        self.session = session
        self.events = ActivityEventRepository(session)
        self.participants = CollaborationParticipantRepository(session)
        self.collaboration = CollaborationService(session)
        self.users = UserRepository(session)
        self.employees = EmployeeRepository(session)

    # --- Resource timeline ----------------------------------------------

    def list_for_resource(
        self,
        user: User,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        *,
        limit: int = _MAX_LIMIT,
    ) -> List[ResolvedActivity]:
        """One resource's timeline. Any participant (viewer+) may read it."""
        self.collaboration.get_access(user, resource_type, resource_id)
        rows = self.events.list_for_resource(
            resource_type.value, resource_id, limit=self._bounded(limit)
        )
        return [self._resolve(row, user) for row in rows]

    # --- Per-user feed ---------------------------------------------------

    def list_for_user(
        self,
        user: User,
        *,
        scope: ActivityScope = ActivityScope.ALL,
        limit: int = _MAX_LIMIT,
    ) -> List[ResolvedActivity]:
        """The user's activity feed across everything they can see."""
        bounded = self._bounded(limit)

        merged: dict[uuid.UUID, ActivityEvent] = {}
        for event in self.events.list_owned(user.id, limit=bounded):
            merged[event.id] = event

        # Resources the user participates in, grouped by type.
        by_type: dict[str, List[uuid.UUID]] = {}
        for row in self.participants.list_for_user(user.id):
            by_type.setdefault(row.resource_type, []).append(row.resource_id)
        for resource_type, ids in by_type.items():
            for event in self.events.list_for_resource_ids(
                resource_type, ids, limit=bounded
            ):
                merged[event.id] = event

        events = self._filter_scope(list(merged.values()), user, scope)
        events.sort(key=lambda e: e.created_at, reverse=True)
        return [self._resolve(e, user) for e in events[:bounded]]

    # --- Helpers ---------------------------------------------------------

    def _filter_scope(
        self, events: List[ActivityEvent], user: User, scope: ActivityScope
    ) -> List[ActivityEvent]:
        if scope is ActivityScope.MINE:
            return [
                e
                for e in events
                if e.actor_type == ActivityActorType.USER.value
                and e.actor_id == user.id
            ]
        if scope is ActivityScope.MENTIONS:
            return [e for e in events if e.kind == ActivityKind.MENTIONED.value]
        return events

    def _resolve(self, event: ActivityEvent, user: User) -> ResolvedActivity:
        is_own = (
            event.actor_type == ActivityActorType.USER.value
            and event.actor_id == user.id
        )
        return ResolvedActivity(
            id=event.id,
            resource_type=CollaborationResourceType(event.resource_type),
            resource_id=event.resource_id,
            kind=ActivityKind(event.kind),
            actor_type=ActivityActorType(event.actor_type),
            actor_id=event.actor_id,
            actor_name=self._actor_name(event.actor_type, event.actor_id),
            summary=event.summary,
            is_own=is_own,
            created_at=event.created_at,
        )

    def _actor_name(
        self, actor_type: str, actor_id: Optional[uuid.UUID]
    ) -> str:
        if actor_type == ActivityActorType.SYSTEM.value or actor_id is None:
            return "System"
        if actor_type == ActivityActorType.EMPLOYEE.value:
            employee = self.employees.get_by_id(actor_id, include_deleted=True)
            return employee.name if employee is not None else "AI employee"
        user = self.users.get_by_id(actor_id)
        if user is None:
            return "Unknown user"
        return user.full_name or user.email

    @staticmethod
    def _bounded(limit: int) -> int:
        return max(1, min(limit, _MAX_LIMIT))
