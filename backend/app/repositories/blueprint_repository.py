"""Data-access layer for :class:`~app.models.blueprint.Blueprint`.

Persistence only — no business logic or authorization. Transaction control is
left to the caller; methods ``flush`` so generated values like ``id`` are
populated.
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.blueprint import Blueprint
from app.schemas.blueprint import BlueprintCreate


class BlueprintRepository:
    """CRUD-style accessors for :class:`Blueprint` rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_blueprint(
        self, employee_id: uuid.UUID, data: BlueprintCreate
    ) -> Blueprint:
        """Persist a new blueprint for ``employee_id``."""
        blueprint = Blueprint(
            employee_id=employee_id,
            vision=data.vision,
            communication_style=data.communication_style,
            personality_traits=data.personality_traits,
            goals=data.goals,
            constraints=data.constraints,
            preferences=data.preferences,
        )
        self.session.add(blueprint)
        self.session.flush()
        self.session.refresh(blueprint)
        return blueprint

    def get_blueprint(self, employee_id: uuid.UUID) -> Optional[Blueprint]:
        """Return the blueprint for ``employee_id``, or ``None`` if absent."""
        stmt = select(Blueprint).where(Blueprint.employee_id == employee_id)
        return self.session.scalar(stmt)

    def update_blueprint(
        self,
        blueprint: Blueprint,
        *,
        vision: Optional[str] = None,
        communication_style: Optional[str] = None,
        personality_traits: Optional[str] = None,
        goals: Optional[str] = None,
        constraints: Optional[str] = None,
        preferences: Optional[str] = None,
    ) -> Blueprint:
        """Apply a partial update to an existing ``blueprint`` instance.

        Only arguments that are not ``None`` are written; unspecified fields
        are left untouched. The ``blueprint`` is assumed to already be loaded
        and authorized by the caller.
        """
        if vision is not None:
            blueprint.vision = vision
        if communication_style is not None:
            blueprint.communication_style = communication_style
        if personality_traits is not None:
            blueprint.personality_traits = personality_traits
        if goals is not None:
            blueprint.goals = goals
        if constraints is not None:
            blueprint.constraints = constraints
        if preferences is not None:
            blueprint.preferences = preferences
        self.session.flush()
        self.session.refresh(blueprint)
        return blueprint
