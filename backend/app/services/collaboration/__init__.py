"""Collaboration Platform services (Sprint 20).

The Collaboration Platform integrates collaboration *across* the existing
domains rather than adding an isolated feature. This slice (20A) ships the
reusable core: a polymorphic participant model, a resolver that reads each
resource's owner back through its *existing* ownership chain, and the access
service that turns "who owns this + who was invited" into an effective role —
never re-implementing an ownership rule that a domain already owns.
"""

from app.services.collaboration.activity_recorder import ActivityRecorder
from app.services.collaboration.activity_service import (
    ActivityScope,
    ActivityService,
    ResolvedActivity,
)
from app.services.collaboration.notification_emitter import NotificationEmitter
from app.services.collaboration.notification_service import (
    NotificationCounts,
    NotificationNotFoundError,
    NotificationService,
    ResolvedNotification,
)
from app.services.collaboration.resources import (
    ResourceRef,
    ResourceResolver,
)
from app.services.collaboration.service import (
    CollaborationAccessDeniedError,
    CollaborationError,
    CollaborationService,
    CollaborationValidationError,
    DuplicateParticipantError,
    ParticipantNotFoundError,
    ResolvedParticipant,
    ResourceNotFoundError,
)
from app.services.collaboration.sharing_service import (
    ShareInactiveError,
    ShareNotFoundError,
    SharingError,
    SharingService,
)

__all__ = [
    "ResourceRef",
    "ResourceResolver",
    "CollaborationService",
    "ResolvedParticipant",
    "CollaborationError",
    "ResourceNotFoundError",
    "CollaborationAccessDeniedError",
    "ParticipantNotFoundError",
    "CollaborationValidationError",
    "DuplicateParticipantError",
    "SharingService",
    "SharingError",
    "ShareNotFoundError",
    "ShareInactiveError",
    "ActivityRecorder",
    "ActivityService",
    "ActivityScope",
    "ResolvedActivity",
    "NotificationEmitter",
    "NotificationService",
    "NotificationCounts",
    "ResolvedNotification",
    "NotificationNotFoundError",
]
