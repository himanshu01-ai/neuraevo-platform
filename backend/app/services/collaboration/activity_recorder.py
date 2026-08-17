"""Activity recorder — the write seam for the timeline (Sprint 20C).

A deliberately small component the collaboration and sharing services hold to
*emit* activity, kept separate from :class:`ActivityService` (which reads) so a
service can record an event without pulling in the read/permission machinery and
without a circular import. It owns only an append repository and a resolver.

It resolves the resource's owner itself when the caller does not supply it, so
callers just say *what happened* and the recorder handles the denormalised
``owner_user_id`` the per-user feed depends on. Recording is best-effort: a
failure to write history must never break the action that happened, so
:meth:`record` swallows and logs rather than raising.
"""

import uuid
from typing import Optional

from app.models.activity_event import ActivityEvent
from app.repositories.activity_event_repository import ActivityEventRepository
from app.services.collaboration.resources import ResourceResolver
from app.utils.constants import (
    ActivityActorType,
    ActivityKind,
    CollaborationResourceType,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ActivityRecorder:
    """Appends activity events, resolving the resource owner as needed."""

    def __init__(self, session) -> None:
        self.session = session
        self.events = ActivityEventRepository(session)
        self.resolver = ResourceResolver(session)

    def record(
        self,
        resource_type: CollaborationResourceType,
        resource_id: uuid.UUID,
        kind: ActivityKind,
        summary: str,
        *,
        actor_type: ActivityActorType = ActivityActorType.USER,
        actor_id: Optional[uuid.UUID] = None,
        owner_user_id: Optional[uuid.UUID] = None,
        commit: bool = True,
    ) -> Optional[ActivityEvent]:
        """Append one event. Best-effort — never raises to its caller.

        ``owner_user_id`` is resolved from the resource when not supplied, so the
        per-user feed can read by owner without a cross-domain scan.
        """
        try:
            if owner_user_id is None:
                ref = self.resolver.load(resource_type, resource_id)
                owner_user_id = ref.owner_user_id if ref is not None else None
            event = ActivityEvent(
                resource_type=resource_type.value,
                resource_id=resource_id,
                owner_user_id=owner_user_id,
                actor_type=actor_type.value,
                actor_id=actor_id,
                kind=kind.value,
                summary=summary,
                sequence=self.events.next_sequence(
                    resource_type.value, resource_id
                ),
            )
            self.events.add(event)
            if commit:
                self.session.commit()
            return event
        except Exception:  # pragma: no cover - defensive; history is best-effort
            logger.exception(
                "Failed to record %s activity for %s %s",
                kind.value,
                resource_type.value,
                resource_id,
            )
            return None
