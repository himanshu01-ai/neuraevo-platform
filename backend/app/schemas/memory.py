"""Pydantic schemas for memory data transfer."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.utils.constants import MemoryType


class MemoryCreate(BaseModel):
    """Input payload for creating a memory.

    ``employee_id`` is taken from the path, not the body.
    """

    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=10000)
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    """Public representation of a memory."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    memory_type: MemoryType
    content: str
    importance_score: float
    created_at: datetime
