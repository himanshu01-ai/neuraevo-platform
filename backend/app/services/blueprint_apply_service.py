"""Blueprint apply service: generate a draft and persist it.

Orchestrates the apply/persist workflow by reusing existing infrastructure —
:class:`BlueprintGenerationService` for the generation pipeline (ownership
validation + Claude generation) and :class:`BlueprintService.update_blueprint`
for partial application and persistence. No generation logic is duplicated.
"""

import uuid

from app.employee_builder.blueprint import BlueprintGenerationProvider
from app.models.blueprint import Blueprint
from app.models.user import User
from app.schemas.blueprint import BlueprintUpdate
from app.services.blueprint_generation_service import BlueprintGenerationService
from app.services.blueprint_service import BlueprintService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BlueprintApplyService:
    """Generates a blueprint draft and applies it to the stored blueprint.

    Ownership validation, generation, draft application, persistence, and the
    transaction are all owned here. The provider is injected (DI).
    """

    def __init__(
        self, session, provider: BlueprintGenerationProvider
    ) -> None:
        self.session = session
        # Reuse the Sprint 4B generation pipeline (ownership + Claude).
        self.generation = BlueprintGenerationService(session, provider)
        # Reuse Sprint 3A blueprint persistence (partial update + commit).
        self.blueprints = BlueprintService(session)

    def apply_generation(
        self, owner: User, employee_id: uuid.UUID
    ) -> Blueprint:
        """Generate a draft and persist it to the employee's blueprint.

        Raises the employee/blueprint ownership errors (404/403) and the
        generation errors (``BlueprintGenerationError`` / ``...TimeoutError``)
        via the reused pipeline. Only non-null draft fields are written, so
        existing blueprint values survive when generation returns null. The
        ``id``, ``employee_id``, and ``created_at`` fields are never modified.
        """
        # Step 1+2: ownership validation + generation (reused pipeline).
        preview = self.generation.preview_generation(owner, employee_id)
        draft = preview.draft

        # Step 3+4: apply only the draft's content fields and persist.
        # BlueprintUpdate carries the same six content fields as the draft;
        # update_blueprint writes only the non-null ones and commits.
        update = BlueprintUpdate(**draft.model_dump())
        blueprint = self.blueprints.update_blueprint(owner, employee_id, update)

        logger.info(
            "User %s applied generated blueprint to employee %s",
            owner.id,
            employee_id,
        )
        return blueprint
