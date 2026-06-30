"""Pydantic schemas for memory data transfer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.utils.constants import MemoryType


class MemoryCreate(BaseModel):
    """Input payload for creating a memory.

    ``employee_id`` is taken from the path, not the body.
    """

    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=10000)
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryUpdate(BaseModel):
    """Partial-update payload for a memory.

    All fields are optional, but at least one must be provided. Fields left
    unset are not modified.
    """

    memory_type: Optional[MemoryType] = None
    content: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    importance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "MemoryUpdate":
        if (
            self.memory_type is None
            and self.content is None
            and self.importance_score is None
        ):
            raise ValueError("At least one field must be provided.")
        return self


class MemoryResponse(BaseModel):
    """Public representation of a memory."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    memory_type: MemoryType
    content: str
    importance_score: float
    created_at: datetime
