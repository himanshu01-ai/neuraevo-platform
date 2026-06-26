"""Blueprint restore service: restore a historical version as current.

Sprint 4E. Atomically snapshots the current blueprint, then overwrites it with
a chosen historical version's values, preserving complete history (nothing is
deleted; exactly one new snapshot is created). Reuses existing ownership
chains; this service owns the transaction. The generation pipeline is not
touched.
"""

import uuid

from app.models.blueprint import Blueprint
from app.models.user import User
from app.repositories.blueprint_repository import BlueprintRepository
from app.repositories.blueprint_version_repository import (
    BlueprintVersionRepository,
)
from app.services.blueprint_service import BlueprintService
from app.services.blueprint_version_service import BlueprintVersionService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlueprintRestoreService:
    """Restores a historical blueprint version, keeping full history."""

    def __init__(self, session) -> None:
        self.session = session
        # Reused for the User -> Employee -> Blueprint ownership chain.
        self.blueprints = BlueprintService(session)
        # Reused for blueprint-scoped version resolution (404 on foreign id).
        self.version_service = BlueprintVersionService(session)
        # Persistence-only repositories; this service owns the transaction.
        self.blueprint_repo = BlueprintRepository(session)
        self.versions = BlueprintVersionRepository(session)

    def restore_version(
        self, owner: User, employee_id: uuid.UUID, version_id: uuid.UUID
    ) -> Blueprint:
        """Restore ``version_id`` as the employee's current blueprint.

        Raises the employee/blueprint ownership errors (404/403) and
        :class:`BlueprintVersionNotFoundError` (404) via the reused chains. On
        success, a snapshot of the current blueprint and the restore overwrite
        are committed together in a single transaction (atomic). Restores only
        the six content fields; ``id``, ``employee_id``, and ``created_at`` are
        never modified.
        """
        # Steps 1-3: ownership validation, blueprint, and scoped version.
        blueprint = self.blueprints.get_blueprint(owner, employee_id)
        version = self.version_service.get_version(
            owner, employee_id, version_id
        )

        # Step 4: snapshot the CURRENT blueprint state before overwriting it.
        next_number = self.versions.count_versions(blueprint.id) + 1
        snapshot = self.versions.create_version(blueprint, next_number)

        # Step 5: apply the requested version's values (full replace incl null).
        self.blueprint_repo.replace_content(
            blueprint,
            vision=version.vision,
            communication_style=version.communication_style,
            personality_traits=version.personality_traits,
            goals=version.goals,
            constraints=version.constraints,
            preferences=version.preferences,
        )

        # Step 6: single commit => snapshot + restore are atomic.
        self.session.commit()
        self.session.refresh(blueprint)

        logger.info(
            "User %s restored blueprint version %s (v%d) for employee %s "
            "(pre-restore snapshot v%d=%s)",
            owner.id,
            version_id,
            version.version_number,
            employee_id,
            next_number,
            snapshot.id,
        )
        return blueprint
