"""Pydantic schemas for blueprint data transfer."""

import uuid
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

# All blueprint text fields share the same optional/max-length constraint.
# An Annotated alias is reused safely across fields/models in Pydantic v2.
BlueprintText = Annotated[Optional[str], Field(default=None, max_length=10000)]


class BlueprintCreate(BaseModel):
    """Input payload for creating a blueprint. All fields optional."""

    vision: BlueprintText = None
    communication_style: BlueprintText = None
    personality_traits: BlueprintText = None
    goals: BlueprintText = None
    constraints: BlueprintText = None
    preferences: BlueprintText = None


class BlueprintUpdate(BaseModel):
    """Partial-update payload for a blueprint. Unset fields are unchanged."""

    vision: BlueprintText = None
    communication_style: BlueprintText = None
    personality_traits: BlueprintText = None
    goals: BlueprintText = None
    constraints: BlueprintText = None
    preferences: BlueprintText = None


class BlueprintResponse(BaseModel):
    """Public representation of a blueprint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    vision: Optional[str] = None
    communication_style: Optional[str] = None
    personality_traits: Optional[str] = None
    goals: Optional[str] = None
    constraints: Optional[str] = None
    preferences: Optional[str] = None
    created_at: datetime
