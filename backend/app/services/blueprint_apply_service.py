"""Blueprint apply service: generate a draft, snapshot, and persist it.

Orchestrates the apply/persist workflow by reusing existing infrastructure —
:class:`BlueprintGenerationService` for the generation pipeline (ownership
validation + Claude generation; left unchanged), the blueprint repository for
the partial update, and the blueprint-version repository for the historical
snapshot. No generation logic is duplicated.

Sprint 4D: every successful apply first snapshots the current blueprint into a
:class:`BlueprintVersion`, then applies the generated draft. The snapshot and
the update are committed together in a single transaction (atomic).
"""

import uuid

from app.employee_builder.blueprint import BlueprintGenerationProvider
from app.models.blueprint import Blueprint
from app.models.user import User
from app.repositories.blueprint_repository import BlueprintRepository
from app.repositories.blueprint_version_repository import (
    BlueprintVersionRepository,
)
from app.services.blueprint_generation_service import BlueprintGenerationService
from app.services.blueprint_service import BlueprintService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlueprintApplyService:
    """Generates a blueprint draft, snapshots history, and persists the draft.

    Ownership validation, generation orchestration, draft application, version
    snapshotting, persistence, and the (atomic) transaction are owned here. The
    provider is injected (DI).
    """

    def __init__(
        self, session, provider: BlueprintGenerationProvider
    ) -> None:
        self.session = session
        # Reuse the Sprint 4B generation pipeline (ownership + Claude).
        self.generation = BlueprintGenerationService(session, provider)
        # Reuse Sprint 3A ownership resolution.
        self.blueprints = BlueprintService(session)
        # Persistence-only repositories; this service owns the transaction.
        self.blueprint_repo = BlueprintRepository(session)
        self.versions = BlueprintVersionRepository(session)

    def apply_generation(
        self, owner: User, employee_id: uuid.UUID
    ) -> Blueprint:
        """Generate a draft, snapshot the current blueprint, then persist.

        Raises the employee/blueprint ownership errors (404/403) and the
        generation errors (``BlueprintGenerationError`` / ``...TimeoutError``)
        via the reused pipeline — in all of those cases nothing is written. On
        success, a historical version snapshot and the blueprint update are
        committed atomically. Only non-null draft fields overwrite existing
        values; ``id``, ``employee_id``, and ``created_at`` are never modified.
        """
        # Step 1+2: ownership validation + generation (reused pipeline).
        # preview_generation is read-only and validates ownership / raises
        # 502/504 before any write is attempted.
        preview = self.generation.preview_generation(owner, employee_id)
        draft = preview.draft

        # Authoritative blueprint to snapshot and update (ownership re-checked).
        blueprint = self.blueprints.get_blueprint(owner, employee_id)

        # Step 3 (atomic with step 4): snapshot the CURRENT blueprint BEFORE
        # applying the update. Both the version insert and the update are
        # flushed now and committed together below.
        version_number = self.versions.count_versions(blueprint.id) + 1
        version = self.versions.create_version(blueprint, version_number)

        # Step 4: apply only the draft's content fields (non-null overwrite).
        self.blueprint_repo.update_blueprint(
            blueprint,
            vision=draft.vision,
            communication_style=draft.communication_style,
            personality_traits=draft.personality_traits,
            goals=draft.goals,
            constraints=draft.constraints,
            preferences=draft.preferences,
        )

        # Single commit => snapshot + update are atomic.
        self.session.commit()
        self.session.refresh(blueprint)

        logger.info(
            "User %s applied generated blueprint to employee %s "
            "(snapshot v%d=%s)",
            owner.id,
            employee_id,
            version_number,
            version.id,
        )
        return blueprint
