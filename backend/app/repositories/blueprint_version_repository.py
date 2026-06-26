"""Data-access layer for
:class:`~app.models.blueprint_version.BlueprintVersion`.

Persistence only — no business logic, ownership, or AI logic. Transaction
control is left to the caller; ``create_version`` ``flush``es so generated
values are populated but does not commit.
"""

import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.blueprint import Blueprint
from app.models.blueprint_version import BlueprintVersion


class BlueprintVersionRepository:
    """Read/insert accessors for :class:`BlueprintVersion` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def count_versions(self, blueprint_id: uuid.UUID) -> int:
        """Return the number of versions stored for ``blueprint_id``."""
        stmt = (
            select(func.count())
            .select_from(BlueprintVersion)
            .where(BlueprintVersion.blueprint_id == blueprint_id)
        )
        return int(self.session.scalar(stmt) or 0)

    def create_version(
        self, blueprint: Blueprint, version_number: int
    ) -> BlueprintVersion:
        """Insert a snapshot of ``blueprint``'s current content fields.

        Copies the values by reference at call time; later mutation of the
        blueprint does not affect the stored snapshot. Does not commit.
        """
        version = BlueprintVersion(
            blueprint_id=blueprint.id,
            version_number=version_number,
            vision=blueprint.vision,
            communication_style=blueprint.communication_style,
            personality_traits=blueprint.personality_traits,
            goals=blueprint.goals,
            constraints=blueprint.constraints,
            preferences=blueprint.preferences,
        )
        self.session.add(version)
        self.session.flush()
        self.session.refresh(version)
        return version

    def get_version(
        self, version_id: uuid.UUID
    ) -> Optional[BlueprintVersion]:
        return self.session.get(BlueprintVersion, version_id)

    def list_versions(
        self, blueprint_id: uuid.UUID
    ) -> Sequence[BlueprintVersion]:
        """Return a blueprint's versions ordered by ``version_number``."""
        stmt = (
            select(BlueprintVersion)
            .where(BlueprintVersion.blueprint_id == blueprint_id)
            .order_by(BlueprintVersion.version_number)
        )
        return self.session.scalars(stmt).all()
