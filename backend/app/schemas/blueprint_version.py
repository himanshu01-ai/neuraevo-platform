"""Pydantic schemas for blueprint version (history) data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BlueprintVersionResponse(BaseModel):
    """Public representation of a blueprint version snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    blueprint_id: uuid.UUID
    version_number: int
    vision: Optional[str] = None
    communication_style: Optional[str] = None
    personality_traits: Optional[str] = None
    goals: Optional[str] = None
    constraints: Optional[str] = None
    preferences: Optional[str] = None
    created_at: datetime
