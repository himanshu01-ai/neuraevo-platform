"""Pydantic schemas for assembled memory context.

A reusable, read-only structure that future AI context-injection sprints can
consume. This sprint performs no AI generation — it only shapes an employee's
memories into context (newest first).
"""

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel

from app.utils.constants import MemoryType


class MemoryContextItem(BaseModel):
    """A single memory reduced to the fields needed for context.

    ``title`` is a short, derived label (the memory model has no title
    column); ``content`` carries the full memory text.
    """

    id: uuid.UUID
    title: str
    content: str
    memory_type: MemoryType
    created_at: datetime


class MemoryContextResponse(BaseModel):
    """Assembled memory context for an employee, ordered newest first."""

    employee_id: uuid.UUID
    memory_count: int
    memories: List[MemoryContextItem]
